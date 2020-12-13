import hashlib
import shutil
import tempfile
import errno
import shlex
from pathlib import Path
import subprocess
import sys
import click
import magic
import pdf2image


class Config:
    def __init__(self):
        self.tesseract_template = 'docker run --rm \
            -v "{INPUT_FILE_PATH}":"/tmp/input/{INPUT_FILE}" \
            jitesoft/tesseract-ocr "/tmp/input/{INPUT_FILE}" stdout'

        self.preview_command_template = "rg \
            --ignore-case --pretty \
            --context 10 '{query}' '{filename}'"
        
        self.data_dir = Path.joinpath(Path.home(), 'docspace')
        self.text_dir = Path.joinpath(self.data_dir, '_text')
        self.text_suffix = '.txt'
        self.md5sum_file = Path.joinpath(self.text_dir, 'md5sums.txt')
    
    def setup(self):
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.text_dir.exists():
            self.text_dir.mkdir(parents=True, exist_ok=True)
        if not self.md5sum_file.exists():
            self.md5sum_file.touch(exist_ok=True)



@click.group()
#@click.option('-c', 'config', type=click.Path(exists=True, file_okay=True))
@click.pass_context
def cli(ctx):
    config = Config()
    config.setup()
    ctx.obj = config


def get_md5sum(file_path: Path):
    with file_path.open(mode="rb") as f:
        file_hash = hashlib.md5()
        while chunk := f.read(8192):
            file_hash.update(chunk)
    return file_hash.hexdigest()

@cli.command('import')
@click.argument('file_paths', type=click.Path(file_okay=True, exists=True),  nargs=-1)
@click.pass_obj
def _import(config: Config, file_paths):
    for file_path in file_paths:
        file_path = Path(file_path).absolute()
        if file_path.is_file():
            if is_not_imported(config, file_path):
                content = get_content(config, file_path)
                __import(config, file_path, content)
            else:
                click.echo(f'{file_path} is already imported, skipping!')

def is_not_imported(config, file_path):
    with config.md5sum_file.open() as f:
        sums = []
        for s in f.readlines():
            sums.append(s.strip())
    new_file_sum = get_md5sum(file_path)
    if new_file_sum in sums:
        return False
    return True

def add_md5sum(config, file_path):
    new_file_sum = get_md5sum(file_path)
    with config.md5sum_file.open('a') as f:
        f.write(new_file_sum + '\n')

def get_content(config: Config, file_path):
    mime_type = magic.from_file(str(file_path), mime=True)

    content = ''
    if mime_type == 'text/plain':
        print('just copy to _text')
        content = get_txt_content(file_path)

    elif mime_type == 'application/pdf':
        print('run tesseract, result to _text')
        content = process_pdf(config, file_path)

    elif mime_type == 'image/png':
        print('run tesseract, result to _text')
        content = run_tesseract(config, file_path)

    elif mime_type == 'image/jpeg':
        print('run tesseract, result to _text')
        content = run_tesseract(config, file_path)

    else:
        print(f'unknown mime type {mime_type}')
    return content


@cli.command()
@click.pass_obj
def reimport_all(config: Config):
    if not click.confirm('this will delete your text cache - continue?', default=False):
        exit(0)
    shutil.rmtree(config.text_dir)
    # recreate folder
    config.setup()

    pathlist = Path(config.data_dir).glob('**/*')
    pathlist = set(pathlist) - set(Path(config.text_dir).glob('**/*'))
    pathlist = pathlist - set([config.text_dir])
    for file_path in pathlist:
        content = get_content(config, file_path)
        __import(config, file_path, content)


def __import(config: Config, file_path: Path, content: str):
    file_name = file_path.name
    destination = Path.joinpath(config.data_dir, file_name)
    counter = 0
    while destination.exists():
        counter += 1
        file_name = file_path.stem + f'_{counter}' + ''.join(file_path.suffixes)
        destination = Path.joinpath(config.data_dir, file_name)

    print(f'copy to {destination}')
    try:
        shutil.copy(file_path, destination)
    except shutil.SameFileError as e:
        pass
    
    text_file = file_name + config.text_suffix
    text_path = Path.joinpath(config.text_dir, text_file)
    print(f'creating text file to {destination}')
    with text_path.open(mode='w+') as f:
        f.write(content)
    add_md5sum(config, file_path)


def get_txt_content(file_path):
    with Path(file_path).open() as f:
        return f.read()

def process_pdf(config, input_path):
    with tempfile.TemporaryDirectory() as tempdir:
        image_paths = convert_pdf_to_images(input_path, tempdir)
        content = ''
        for path in image_paths:
            content += run_tesseract(config, path)
    return content

def convert_pdf_to_images(input_path, tempdir):
    images = pdf2image.convert_from_path(input_path)
    paths = []
    for num, img in enumerate(images): 
        path = f'{tempdir}/output_{num}.jpg'
        img.save(path, 'JPEG')
        paths.append(path)
    return paths

def run_tesseract(config:Config, input_file_path):
    input_filename = Path(input_file_path).name
    tesseract_command = shlex.split(
            config.tesseract_template.format(
                INPUT_FILE_PATH=input_file_path, 
                INPUT_FILE=input_filename))
    output = subprocess.check_output(tesseract_command)
    return output.decode()



def launch_fzf(config: Config):
    content = []
    pathlist = Path(config.text_dir).glob('**/*' + config.text_suffix)
    for path in pathlist:
        filename = text_file_path_to_doc_path(config, path)
        for line in path.open().readlines():
            if line.strip():
                content.append(f'{filename}:{line}')

    python_executable = sys.executable
    script = sys.argv[0]
    # we have to launch the preview parser as an external program
    preview_preprocess_command = '%s %s _parse_preview {} {q}' % (
        python_executable, script)
    output = subprocess.check_output(
        ('fzf', '--reverse', '--multi', '--ansi', '--preview', f"{preview_preprocess_command}"), input=''.join(content).encode())
    print(output)


def text_file_path_to_doc_path(config: Config, textfilepath):
    filename = textfilepath.name
    filename = filename[:-len(config.text_suffix)]
    return filename


def docpath_to_textfilepath(config: Config, docfilepath):
    filename = Path.joinpath(config.text_dir, f'{docfilepath}.txt')
    return filename



@cli.command('_parse_preview')
@click.argument('line')
@click.argument('current_query')
@click.pass_obj
def _parse_preview(config: Config, line, current_query):
    """
    called by fzf to get the preview
    """
    filename, content = line.split(':', 1)
    filename = docpath_to_textfilepath(config, filename)
    preview_command = shlex.split(
        config.preview_command_template.format(filename=filename, query=content))
    try:
        output = subprocess.check_output(preview_command)
        print(output.decode())
    except subprocess.CalledProcessError as e:
        print(e)
    except OSError as e:
        if e.errno == errno.ENOENT:
            click.secho(f'error calling {preview_command}:', fg='red')
            click.echo(e)
            click.echo()
            with Path(filename).open() as f:
                print(f.read())


@cli.command()
@click.pass_obj
def search(config: Config):
    launch_fzf(config)


cli()
