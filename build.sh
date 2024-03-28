#!/bin/bash
# @name FlatPakBuildScript
# @brief This script provides functionality to build and run this project as a flatpak package, from either a host, or a container environment.
# @example
#   ./build.sh

set -eo pipefail

# @description Colored output for error messages
# @arg $1 string Message
# @exitcode 0
# @stderr Formatted message
function err() {
    local C_RED_BOLD="\e[1;31m"
    local C_RED="\e[0;31m"
    local C_RESET="\e[0m"
    local C_MESSAGE
    C_MESSAGE="${1}"
    echo -e "${C_RED_BOLD}ERROR: ${C_RESET}${C_RED}${C_MESSAGE}${C_RESET}" >&2
}

# @description Colored output for informational messages
# @arg $1 string Message
# @exitcode 0
# @stdout Formatted message
function info() {
    local C_BLUE="\e[0;34m"
    local C_RESET="\e[0m"
    local C_MESSAGE
    C_MESSAGE="${1}"
    echo -e "${C_BLUE}${C_MESSAGE}${C_RESET}"
}

# @description Colored output for warning messages
# @arg $1 string Message
# @exitcode 0
# @stdout Formatted message
function warning() {
    local C_YELLOW_BOLD="\e[1;33m"
    local C_YELLOW="\e[0;33m"
    local C_RESET="\e[0m"
    local C_MESSAGE
    C_MESSAGE="${1}"
    echo -e "${C_YELLOW_BOLD}WARNING: ${C_RESET}${C_YELLOW}${C_MESSAGE}${C_RESET}"
}

# @description Colored output for success messages
# @arg $1 string Message
# @exitcode 0
# @stdout Formatted message
function success() {
    local C_GREEN_BOLD="\e[1;32m"
    local C_GREEN="\e[0;32m"
    local C_RESET="\e[0m"
    local C_MESSAGE
    C_MESSAGE="${1}"
    echo -e "${C_GREEN_BOLD}SUCCESS: ${C_RESET}${C_GREEN}${C_MESSAGE}${C_RESET}"
}

# @description Trap function for error handling
# @arg $1 int Line number
# @arg $2 int Exit code
function error_trap() {
    local line_number=$1
    local exit_code=$2
    error "Error at line ${line_number}; exit code: ${exit_code}"
    exit ${exit_code}
}
trap 'error_trap ${LINENO} $?' ERR

# @description Check if a command exists
# @arg $1 string Command name
# @exitcode 0 If the command exists
# @exitcode 1 If the command does not exist
function check_command() {
    if ! command -v $1 &> /dev/null; then
        return 1
    else 
        return 0
    fi
}

# @description Execute a flatpak command in the appropriate environment
# @arg $1 string Command
# @exitcode 0 If the command is executed successfully
# @exitcode 1 If the command is not executed successfully
# @stderr Status of the function execution
function exec_flatpak() {
    local command
    command="${*}"
    if [ -z "${command}" ]; then
        err "No command provided"
        return 1
    fi
    local environment
    if [ -f "/run/.containerenv" ]; then
        environment="CONTAINER"
    else
        environment="HOST"
    fi
    info "[${environment}] Executing flatpak command: flatpak ${command}"
    case "${environment}" in
        HOST)
            flatpak ${command}
            return $?
            ;;
        CONTAINER)
            if check_command "flatpak-spawn"; then
                flatpak-spawn --host flatpak ${command}
                return $?
            elif check_command "host-spawn"; then
                host-spawn flatpak ${command}
                return $?
            fi
            ;;
        *)
            err "Invalid environment type provided (one of: HOST, CONTAINER)"
            return 1
            ;;
    esac
}

# @description Check if a flatpak repository exists
# @arg $1 string Repository name
# @exitcode 0 If the repository exists
# @exitcode 1 If the repository does not exist
# @stderr Status of the function execution
function check_flatpak_repository() {
    local repository
    repository="${1}"
    if [ -z "${repository}" ]; then
        err "No repository provided"
        return 1
    fi
    local uri
    uri="${2}"
    if [ -z "${uri}" ]; then
        err "No repository URI provided"
        return 1
    fi
    if ! exec_flatpak --user remote-list | grep -qi "${repository}"; then
        warning "Flatpak repository ${repository} does not exist"
        return 1
    fi
    if ! exec_flatpak --user remote-list | grep -qi "${uri}"; then
        warning "Flatpak repository ${repository} URI does not match"
        return 1
    fi
    info "Flatpak repository ${repository} is OK"
    return 0
}

# @description Check if a flatpak package is installed
# @arg $1 string Package name
# @exitcode 0 If the package is installed
# @exitcode 1 If the package is not installed
# @stderr Status of the function execution
function check_flatpak_package() {
    local package
    package="${1}"
    if [ -z "${package}" ]; then
        err "No package name provided"
        return 1
    fi
    if ! exec_flatpak --user list | grep -qi "${package}"; then
        warning "Flatpak package ${package} is not installed"
        return 1
    fi
    info "Flatpak package ${package} is OK"
    return 0
}

# @description Install a flatpak repository
# @arg $1 string Repository name
# @arg $2 string Repository URI
# @exitcode 0 If the repository is installed
# @exitcode 1 If the repository is not installed
# @stderr Status of the function execution
function install_flatpak_repository() {
    local repository
    repository="${1}"
    if [ -z "${repository}" ]; then
        err "No repository provided"
        return 1
    fi
    local uri
    uri="${2}"
    if [ -z "${uri}" ]; then
        err "No repository URI provided"
        return 1
    fi
    if check_flatpak_repository "${repository}" "${uri}"; then
        return 0
    fi
    info "Adding flatpak repository: ${repository}"
    if ! exec_flatpak --user remote-add --if-not-exists ${repository} ${uri}; then
        err "Failed to add flatpak repository ${repository}"
        return 1
    else
        success "Flatpak repository ${repository} added successfully"
        return 0
    fi
}

# @description Ensure a flatpak package is installed
# @arg $1 string Package name
# @exitcode 0 If the package is installed
# @exitcode 1 If the package is not installed
# @stderr Status of the function execution
function install_flatpak_package() {
    local package
    package="${1}"
    if [ -z "${package}" ]; then
        err "No package name provided"
        return 1
    fi
    if check_flatpak_package "${package}"; then
        return 0
    fi
    info "Installing flatpak package: ${package}"
    if ! exec_flatpak install --user flathub "${package}" -y; then
        err "Failed to install flatpak package ${package}"
        return 1
    else
        success "Flatpak package ${package} installed successfully"
        return 0
    fi
}

# @description Build a flatpak package
# @arg $1 string Package configuration file
# @exitcode 0 If the package is built successfully
# @exitcode 1 If the package is not built successfully
# @stderr Status of the function execution
function build_flatpak() {
    local package_config
    package_config="${1}"
    if [ -z "${package_config}" ]; then
        err "No package configuration file provided"
        return 1
    fi
    if [ ! -f "${package_config}" ]; then
        err "Package configuration file: ${package_config} does not exist"
        return 1
    fi
    local environment
    if [ -f "/run/.containerenv" ]; then
        environment="CONTAINER"
    else
        environment="HOST"
    fi
    # Ensure build dependencies are installed
    install_flatpak_repository "flathub" "https://flathub.org/repo/flathub.flatpakrepo"
    install_flatpak_package "org.flatpak.Builder"
    info "Building flatpak package using configuration: ${package_config}..."
    if ! exec_flatpak run org.flatpak.Builder --install --install-deps-from=flathub --default-branch=master --force-clean --user build-dir ${package_config}; then
        err "Failed to build flatpak package"
        return 1
    else
        success "Flatpak package built successfully"
        return 0
    fi
}

# @description Run a flatpak package
# @arg $1 string Package name
# @exitcode 0 If the package is run successfully
# @exitcode 1 If the package is not run successfully
# @stderr Status of the function execution
function run_flatpak() {
    local package_name
    package_name="${1}"
    if [ -z "${package_name}" ]; then
        err "No package name provided"
        return 1
    fi
    if ! check_flatpak_package "${package_name}"; then
        return 1
    fi
    if ! exec_flatpak run "${package_name}" ; then
        err "Failed to test-run flatpak package"
        return 1
    else
        success "Flatpak package test-ran successfully"
        return 0
    fi
}

build_flatpak "com.usebottles.bottles.yml"
run_flatpak "com.usebottles.bottles"
