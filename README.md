# SuperISOUpdater-Fork

**SuperISOUpdater2** is a Windows-friendly tool to conveniently update all of your ISO files for Ventoy and other bootable media. This is an upgrade of [SuperISOUpdater](https://github.com/JoshuaVandaele/SuperISOUpdater), with new features and improved reliability. :)

## Features

- Automatic download and update of popular OS and utility ISOs
- Robust download with resume, retries, and integrity checks
- Easy to use on Windows (no Linux knowledge required)
- CLI interface with retry options (`-r 10` for 10 retries, `-r ALL` for infinite retries)
- Modern Python 3.10+ codebase

## Installation (Windows)

1. **Install Python 3.10 or newer** from [python.org](https://www.python.org/downloads/windows/).
2. Download or clone this repository.
3. Open Command Prompt in the project folder.
4. Install required packages:
   ```
   pip install -r requirements.txt
   ```
5. (Optional) To install as a command:
   ```
   pip install .
   ```

## Usage (Windows)

You do **not** need to install the package to use it! After installing the requirements, you can run the updater directly:

```
python sisou2.py /path_to_ventoy [options]
```

If it is installed, you can use the binaries anywhere !
```
sisou2 /path_to_ventoy [options]
```

## Installation & Usage (Linux, recommended: pipx)

The recommended way to install and use SuperISOUpdater2 on Linux is with [pipx](https://pypa.github.io/pipx/):


### 1. Install SuperISOUpdater2 with pipx
Just run this in your project directory:
```bash
sh linux_install_with_pipx.sh
```
This script will install pipx if needed and set up the command for you.

### 2. Run the updater from anywhere
```bash
sisou2 /path_to_ventoy [options]
```

If you want to use a virtual environment instead (portable, only on ext4):
```bash
sh create_venv_for_linux.sh
.venv/bin/python sisou2.py /path_to_ventoy [options]
```

### Examples

- Retry up to 10 times:
  ```
  python sisou2.py D:\path\to\ventoy -r 10
  ```
- Infinite retries:
  ```
  python sisou2.py D:\path\to\ventoy -r ALL
  ```

## Configuration

Edit `config.toml.default` to customize which ISOs are updated and where they are stored.
(The config will copy itself to the ventoy location)

## Uninstallation

### Windows:
If you installed with pip:
```
pip uninstall superisoupdater2
```
If you only used requirements.txt, just delete the project folder.

### If installed with pipx (Linux):
```bash
pipx uninstall sisou2
```


## Contributing

Pull requests and issues are welcome!
See [https://github.com/lostallmymoney/SuperISOUpdater2](https://github.com/lostallmymoney/SuperISOUpdater2) for the latest source and bug tracker.

Props to [JoshuaVandaele](https://github.com/JoshuaVandaele) for SISOU original : https://github.com/JoshuaVandaele/SuperISOUpdater

## License

GPLv3 © 2025 lostallmymoney
