#!/bin/bash

VENV_NAME="fuzzy-macro-env"
VENV_PATH="$HOME/$VENV_NAME"

create_virtual_env() {
    if [ ! -d "$VENV_PATH" ]; then
        printf "\033[1;35mCreating virtual environment at $VENV_PATH\033[0m\n"
        "$PYTHON_CMD" -m venv "$VENV_PATH"
    else
        printf "\033[1;32mVirtual environment already exists at $VENV_PATH\033[0m\n"
    fi
}

activate_virtual_env() {
    printf "\033[1;35mActivating virtual environment\033[0m\n"
    source "$VENV_PATH/bin/activate"
}

# Run the venv's pip directly. A venv moved from where it was created still points
# `activate` at the old path, so a bare `pip` would fall through to another Python.
venv_pip() {
    "$VENV_PATH/bin/python" -m pip "$@"
}

install_pip_package() {
	local packages="$1"
	local extra_args="$2"
	local tmp_constraint=""

	if [ -n "$constraints" ]; then
		tmp_constraint=$(mktemp)
		printf "%s\n" "$constraints" > "$tmp_constraint"
		constraint_arg="--constraint $tmp_constraint"
	else
		constraint_arg=""
	fi

	if [ "$chip" = "arm64" ]; then
		arch -arm64 "$VENV_PATH/bin/python" -m pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 $extra_args $packages $constraint_arg
	else
		#fallback for other architectures
		venv_pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 $extra_args $packages $constraint_arg
	fi
	local status=$?

	if [ -n "$tmp_constraint" ] && [ -f "$tmp_constraint" ]; then
		rm -f "$tmp_constraint"
	fi
	return "$status"
}

# Stop instead of printing "Installation complete!" when pip failed.
pip_failed() {
	printf "\033[31;1mInstalling the libraries failed. Fix the error above, then run this installer again.\033[0m\n"
	exit 1
}

upgrade_pip_tools() {
    if [ "$chip" = "arm64" ]; then
        arch -arm64 "$PYTHON_CMD" -m pip install --upgrade pip setuptools wheel
    else
        "$PYTHON_CMD" -m pip install --upgrade pip setuptools wheel
    fi
}

#get system information
chip=$(arch)
os_ver=$(sw_vers -productVersion)

# BSD sort on macOS supports version sorting.  The old checks compared the
# result to an exact version (for example, 10.15.0), which misclassified every
# later patch release such as Catalina 10.15.7 and Monterey 12.3.3.
version_at_least() {
	[ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

#check mac compatibility

if [ "$chip" = 'arm64' ]; then
	if ! version_at_least "$os_ver" "13.0.0"; then
		printf "\033[31;1mYour mac is not compatible. It has to be Ventura or later. Consider updating it. \033[0m\n"
		exit 1
	fi
else 
	if ! version_at_least "$os_ver" "10.12.0"; then
		printf "\033[31;1mYour mac is not compatible. It has to be 10.12 or later. Consider updating it. \033[0m\n"
		exit 1
	fi
fi

printf "\033[32;1mYour mac is compatible \033[0m\n\n\n"

#Check if python ver is installed

python_ver="3.9"
python_link="/www.python.org/ftp/python/3.9.8/python-3.9.8-macos11.pkg"
constraints=$'numpy<2'
if [ "$chip" = 'i386' ]; then
	if version_at_least "$os_ver" "12.0.0"; then
		python_ver="3.8"
		python_link="/www.python.org/ftp/python/3.8.0/python-3.8.0-macosx10.9.pkg"
		constraints=$'numpy<2\npyobjc-core<11.0\npyobjc<11.0'
	elif version_at_least "$os_ver" "10.15.0"; then
		python_ver="3.8"
		python_link="/www.python.org/ftp/python/3.8.0/python-3.8.0-macosx10.9.pkg"
		constraints=$'numpy<2\npyobjc-core<11.0\npyobjc<11.0'
	else 
		python_ver="3.7"
		python_link="/www.python.org/ftp/python/3.7.9/python-3.7.9-macosx10.9.pkg"
		constraints=$'numpy<2\npyobjc-core<10.0\npyobjc<10.0'
	fi
fi

# Only use a framework build of Python (python.org's, which the .pkg above installs, or
# Homebrew's). A python3.9 found on PATH can be a pyenv shim, which is not a framework build,
# and a venv built from that is slow and has no Python Dock icon.
PYTHON_CMD="/Library/Frameworks/Python.framework/Versions/${python_ver}/bin/python${python_ver}"
brew_python="$(brew --prefix 2>/dev/null)/opt/python@${python_ver}/bin/python${python_ver}"
if [ ! -x "$PYTHON_CMD" ] && [ -x "$brew_python" ]; then
	PYTHON_CMD="$brew_python"
fi

filename=$(echo "${python_link}" | sed -e 's/\/.*\///g')

if "$PYTHON_CMD" --version; then
	printf "\033[1;32mPython is already installed\033[0m\n"
		if [ "$chip" = "arm64" ]; then
			# Resolve the real python executable (pyenv shims may point to a shim script)
			python_exec=$("$PYTHON_CMD" -c 'import sys; print(sys.executable)' 2>/dev/null || true)
			if [ -n "$python_exec" ] && [ -x "$python_exec" ]; then
				arch_output=$(file "$python_exec" 2>/dev/null || true)
				py_platform=$("$PYTHON_CMD" -c 'import platform; print(platform.machine())' 2>/dev/null || true)
			else
				python_exec="$PYTHON_CMD"
				arch_output=$(file "$python_exec" 2>/dev/null || true)
				py_platform=
			fi

			if echo "$py_platform" | grep -qi "arm64" || echo "$arch_output" | grep -q "arm64"; then
				echo -e "\033[1;32mPython $python_ver has an arm64 binary\033[0m"
			else
				echo -e "\033[1;31mThere are no arm64 binaries for Python $python_ver!\033[0m"
				echo -e "\033[1;33mFix: reinstall Python 3.9 with arm64 binaries (brew, miniforge) or use a universal/arm64 build.\033[0m"
			fi
		fi
else
	printf "\033[1;35mPython is not installed, installing python ${python_ver}\nThere should be a popup for the python installer.\n\033[0m"
	curl -O "https:/${python_link}" && open "${filename}"
	# Wait until python installation has finished.
	until "$PYTHON_CMD" --version &> /dev/null; do
	  sleep 5;
	done
	#printf "\033[1;35mPress enter to continue when python is installed\033[0m"
	#read
fi

if xcode-select --print-path &> /dev/null; then
	printf "\033[1;32mCommand Line Tools are already installed.\033[0m\n"
else
	printf "\033[1;35mInstall Command Line Tools. There should be a pop-up; click the install button.\033[0m\n"
	xcode-select --install
	# Wait until XCode Command Line Tools installation has finished.
	until xcode-select --print-path &> /dev/null; do
	  sleep 5
	done
fi

#echo "Enter your password (the password used to log into the admin user). Note: the password is not visible"
#sudo xcode-select --switch /Library/Developer/CommandLineTools
printf "\033[1;35mMaking sure pip is installed\033[0m\n\n"
"$PYTHON_CMD" -m ensurepip
"$PYTHON_CMD" -m pip cache purge
upgrade_pip_tools

printf "\033[1;35mInstalling SSL certificates for Python\033[0m\n"

#find and run the Install Certificates command for the specific Python version
cert_command="/Applications/Python ${python_ver}/Install Certificates.command"
if [ -f "$cert_command" ]; then
	printf "\033[1;32mFound certificate installer for Python ${python_ver}\033[0m\n"
	"$cert_command"
else
	printf "\033[1;31mDid not find certificate installer for Python ${python_ver}\033[0m\n"
fi

attempt=1
while [ "$attempt" -le 3 ]; do
	create_virtual_env
	activate_virtual_env
	
	# Validate Python and pip paths inside the venv
	if [ -x "$VENV_PATH/bin/python" ] && [ -x "$VENV_PATH/bin/pip" ]; then
		echo -e "\033[1;32mVirtual environment is valid\033[0m"
		break
	else
		echo -e "\033[1;31mVirtual environment is broken, recreating...\033[0m"
		rm -rf "$VENV_PATH"
		((attempt++))
		sleep 2
		
	fi
done

venv_pip install --upgrade pip setuptools wheel
printf "\033[1;35mInstalling libraries\033[0m\n\n"

# Everything is installed in one pip call at the end so pip resolves it together, and the
# numpy<2 below (and the constraints file) keeps numpy below 2. Each branch below adds its own
# packages. Only easyocr gets a separate call because it needs --no-deps.
packages="numpy<2 pyautogui pillow discord-webhook pypresence fuzzywuzzy python-Levenshtein pyscreeze<0.1.29 gevent eel requests pynput psutil"
# Wheels built for macOS 10.12 on Intel (github.com/Fuzzy-Team/Fuzzy-Macro-Wheels). PyPI has no
# Intel OpenCV wheel that runs on macOS 10.12-11 and loads the AI Gather ONNX models (they need
# OpenCV 4.8+), and its aiohttp 3.7.4 has none below 10.14. pip checks the sha256 after the #.
wheels="https://github.com/Fuzzy-Team/Fuzzy-Macro-Wheels/releases/download/legacy-macos-3"
if [ "$python_ver" = '3.7' ]; then
	# discord.py 2.x needs Python 3.8. 1.7.3 has no slash commands, so the bot runs them as
	# fuzz! prefix commands (modules/discord_bot/legacyCommands.py). It needs aiohttp below 3.8;
	# 3.7.4.post0 is the newest.
	# mss 9.0.1 needs Python 3.8, so Python 3.7 takes the newest mss it supports.
	packages="$packages discord.py==1.7.3 $wheels/aiohttp-3.7.4.post0-cp37-cp37m-macosx_10_12_x86_64.whl#sha256=5d232cc01fbe8ae0d69c2680ea32af55e0283abfe2a31ce7d3121d296dacd711 mss"
else
	packages="$packages discord.py aiohttp==3.10.5 mss==9.0.1"
fi

if [ "$python_ver" = '3.9' ] || { [ "$python_ver" = '3.8' ] && version_at_least "$os_ver" "12.0.0"; }; then
	# This installs the latest opencv-headless below 4.11.
	# Core ML models run through the system framework, so coremltools is not needed
	packages="$packages opencv-python-headless<4.11 ocrmac pyobjc-framework-CoreML pyobjc-framework-ColorSync<12.0 pyobjc-framework-ApplicationServices"
	# Nothing on this path uses these anymore: torch (from before coremltools stopped needing it),
	# scipy/PyWavelets (came with ImageHash), coremltools and what it pulled in, Flask (stream.py
	# uses the standard library), and the dependencies of matplotlib, httpx and torch.
	# Only this path removes them; the older Intel paths still need torch and its dependencies.
	venv_pip uninstall -y torch torchvision scipy PyWavelets \
		coremltools sympy mpmath protobuf tqdm pyaml PyYAML cattrs exceptiongroup \
		flask werkzeug jinja2 markupsafe itsdangerous blinker \
		networkx fsspec filelock fonttools contourpy kiwisolver cycler python-dateutil \
		anyio httpcore h11 websocket-client

elif version_at_least "$os_ver" "10.15.0"; then
	printf "\033[1;35mInstalling rust\n\n\033[0m"
	curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
	source "$HOME/.cargo/env"

	# Keep exactly one OpenCV package installed because all variants share the cv2 namespace.
	# pip replaces an installed opencv-python itself, so only the other variants are removed.
	venv_pip uninstall -y opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
	install_pip_package "easyocr" "--no-deps" || pip_failed
	packages="$packages $wheels/opencv_python-4.11.0.86-cp38-cp38-macosx_10_12_x86_64.whl#sha256=83bc5c4a45b494e6ef33a88dd22c0527df88d05e77e2e66b37bb4038fff3aa55 torch torchvision>=0.5 scipy shapely ninja pyclipper python-bidi scikit-image PyYAML pyobjc-framework-ColorSync<12.0 pyobjc-framework-ApplicationServices"

else
	# Apple Vision OCR needs macOS 10.15, so use easyocr. 1.7.1 is the last release that
	# works with python-bidi 0.4.2 (the newest for Python 3.7), and torch 1.13.1 is the last
	# for Python 3.7. --no-deps keeps easyocr from adding a second OpenCV package and
	# scikit-image (its wheels need macOS 10.15; ocr.py stands in for it).
	install_pip_package "pyobjc-framework-ColorSync<11.0 pyobjc-framework-ApplicationServices<11.0 easyocr==1.7.1" "--no-deps" || pip_failed
	packages="$packages pyobjc-core<11.0 pyobjc-framework-Cocoa<11.0 $wheels/opencv_python-4.11.0.86-cp37-cp37m-macosx_10_12_x86_64.whl#sha256=6fa718f43386ab0f9d1435592229bb36b53f701d141b70ff048b706e0dd2a4f6 torch==1.13.1 torchvision==0.14.1 scipy shapely pyclipper python-bidi==0.4.2 PyYAML ninja packaging"
fi
install_pip_package "$packages" || pip_failed
# no longer used; ocrmac imports matplotlib whenever it is installed, slowing startup
venv_pip uninstall -y matplotlib html2image httpx ImageHash

"$VENV_PATH/bin/python" << "EOF"

# install_certifi.py
#
# sample script to install or update a set of default Root Certificates
# for the ssl module.  Uses the certificates provided by the certifi package:
#       https://pypi.org/project/certifi/

import os
import os.path
import ssl
import stat
import subprocess
import sys

STAT_0o775 = ( stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
             | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
             | stat.S_IROTH |                stat.S_IXOTH )

def main():
    openssl_dir, openssl_cafile = os.path.split(
        ssl.get_default_verify_paths().openssl_cafile)

    print(" -- pip install --upgrade certifi")
    subprocess.check_call([sys.executable,
        "-E", "-s", "-m", "pip", "install", "--upgrade", "certifi"])

    import certifi

    # change working directory to the default SSL directory
    os.chdir(openssl_dir)
    relpath_to_certifi_cafile = os.path.relpath(certifi.where())
    print(" -- removing any existing file or link")
    try:
        os.remove(openssl_cafile)
    except FileNotFoundError:
        pass
    print(" -- creating symlink to certifi certificate bundle")
    os.symlink(relpath_to_certifi_cafile, openssl_cafile)
    print(" -- setting permissions")
    os.chmod(openssl_cafile, STAT_0o775)
    print(" -- update complete")

if __name__ == '__main__':
    main()
EOF
printf "\n\n\n\033[32;1mInstallation complete!\033[0m\n"
