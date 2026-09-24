#!/bin/bash

VENV_NAME="fuzzy-macro-env"
VENV_PATH="$HOME/$VENV_NAME"

create_virtual_env() {
    if [ ! -d "$VENV_PATH" ]; then
        printf "\033[1;35mCreating virtual environment at $VENV_PATH\033[0m\n"
        python"${python_ver}" -m venv "$VENV_PATH"
    else
        printf "\033[1;32mVirtual environment already exists at $VENV_PATH\033[0m\n"
    fi
}

activate_virtual_env() {
    printf "\033[1;35mActivating virtual environment\033[0m\n"
    source "$VENV_PATH/bin/activate"
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
		arch -arm64 pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 $extra_args $packages $constraint_arg
	else
		#fallback for other architectures
		pip install --prefer-binary --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --default-timeout=100 $extra_args $packages $constraint_arg
	fi

	if [ -n "$tmp_constraint" ] && [ -f "$tmp_constraint" ]; then
		rm -f "$tmp_constraint"
	fi
}

upgrade_pip_tools() {
    if [ "$chip" = "arm64" ]; then
        arch -arm64 python"${python_ver}" -m pip install --upgrade pip setuptools wheel
    else
        python"${python_ver}" -m pip install --upgrade pip setuptools wheel
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

filename=$(echo "${python_link}" | sed -e 's/\/.*\///g')

if python"${python_ver}" --version; then
	printf "\033[1;32mPython is already installed\033[0m\n"
		if [ "$chip" = "arm64" ]; then
			# Resolve the real python executable (pyenv shims may point to a shim script)
			python_exec=$(python"${python_ver}" -c 'import sys; print(sys.executable)' 2>/dev/null || true)
			if [ -n "$python_exec" ] && [ -x "$python_exec" ]; then
				arch_output=$(file "$python_exec" 2>/dev/null || true)
				py_platform=$(python"${python_ver}" -c 'import platform; print(platform.machine())' 2>/dev/null || true)
			else
				python_exec=$(which python${python_ver} 2>/dev/null || true)
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
	until python"${python_ver}" --version &> /dev/null; do
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
python"${python_ver}" -m ensurepip
python"${python_ver}" -m pip cache purge
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

pip install --upgrade pip setuptools wheel
install_pip_package "numpy<2"
printf "\033[1;35mInstalling libraries\033[0m\n\n"

if [ "$python_ver" = '3.9' ] || { [ "$python_ver" = '3.8' ] && version_at_least "$os_ver" "12.0.0"; }; then
	# Use pip --force-reinstall to ensure a compatible opencv and numpy
	# This installs the latest opencv-headless below 4.11 and enforces numpy<2
	install_pip_package "opencv-python-headless<4.11 numpy<2" "--force-reinstall"
	# coremltools only needs torch to convert PyTorch models, not to run the macro's models
	install_pip_package "coremltools"
	install_pip_package "ocrmac"
	install_pip_package "pyobjc-framework-ColorSync<12.0"
	install_pip_package "pyobjc-framework-ApplicationServices"
	# torch was installed here before coremltools stopped needing it, and scipy/PyWavelets
	# only came with ImageHash. Nothing on this path uses them anymore.
	pip uninstall -y torch torchvision scipy PyWavelets

elif version_at_least "$os_ver" "10.15.0"; then
	printf "\033[1;35mInstalling rust\n\n\033[0m"
	curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
	source "$HOME/.cargo/env"

	# OpenCV 4.4 and 4.6 cannot load the current AI Gather ONNX models.
	# OpenCV 4.10 has a compatible macOS 10.15 Intel wheel. Keep exactly one
	# OpenCV package installed because all variants share the cv2 namespace.
	pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
	install_pip_package "opencv-python==4.10.0.84 numpy==1.19.1" "--force-reinstall"
	install_pip_package "easyocr" "--no-deps"
	install_pip_package "torch"
	install_pip_package "torchvision>=0.5"
	install_pip_package "scipy shapely ninja pyclipper python-bidi scikit-image PyYAML"
	install_pip_package "pyobjc-framework-ColorSync<12.0"
	install_pip_package "pyobjc-framework-ApplicationServices"
	
else
	install_pip_package "pyobjc-core<11.0"
	install_pip_package "pyobjc-framework-Cocoa<11.0"
	install_pip_package "pyobjc-framework-ColorSync<11.0" "--no-deps"
	install_pip_package "pyobjc-framework-ApplicationServices<11.0" "--no-deps"
	# No 4.6 wheel exists below macOS 10.15, so pip builds it from source here (slow, but known
	# to work down to 10.12, unlike the older wheels, which bundle libraries built for 10.13).
	install_pip_package "opencv-python==4.6.0.66"
	# Apple Vision OCR needs macOS 10.15, so use easyocr. 1.7.1 is the last release that
	# works with python-bidi 0.4.2 (the newest for Python 3.7), and torch 1.13.1 is the last
	# for Python 3.7. --no-deps keeps easyocr from adding a second OpenCV package and
	# scikit-image (its wheels need macOS 10.15; ocr.py stands in for it).
	install_pip_package "easyocr==1.7.1" "--no-deps"
	install_pip_package "torch==1.13.1 torchvision==0.14.1 scipy shapely pyclipper python-bidi==0.4.2 PyYAML ninja packaging"
fi
install_pip_package "pyautogui"
install_pip_package "mss"
install_pip_package "pillow"
install_pip_package "discord-webhook"
install_pip_package "discord.py"
install_pip_package "pypresence"
install_pip_package "fuzzywuzzy"
install_pip_package "python-Levenshtein"
install_pip_package "pyscreeze<0.1.29"
install_pip_package "gevent"
install_pip_package "eel"
install_pip_package "flask"
install_pip_package "pygetwindow"
install_pip_package "requests" #used to check if this script was ran, should be installed by discord-webhooks
install_pip_package "aiohttp==3.10.5"
install_pip_package "pynput"
# no longer used; ocrmac imports matplotlib whenever it is installed, slowing startup
pip uninstall -y matplotlib html2image httpx ImageHash
install_pip_package "numpy<2" "--force-reinstall"

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
