#!/bin/bash
# @name FlatPakBuildScript
# @brief This script provides functionality to build and run this project as a flatpak package, from either a host, or a container environment.
# @example
#   1. This command will build, and run the flatpak package as the current user, and display the help message for the bottles-cli command:
#
#     ./build.sh build -r -u -c bottles-cli -a --help
#
#   2. This command will run the flatpak package as the current user, and run bottles in GUI-interactive mode:
#
#   ./build.sh run -r -u -c bottles
#
#   3. This command will display the help message for the build action:
#
#   ./build.sh build -h

set -eo pipefail

BUILD=false
RUN=false
USERMODE=false
AARGS=false
BARGS=()
COMMAND=""

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

# @description Display usage information
# @arg $1 string Action
# @exitcode 0
# @stdout Usage information
function usage() {
    local action
    action="${1}"
    action=$(echo "${action}" | tr '[:lower:]' '[:upper:]')
    echo "Bottles Flatpak Build Script"
    case "${action}" in
        BUILD)
            echo "Usage: $0 ACTION [OPTIONS] [ARGS]"
            echo -e "\nHelp for build action:\n"
            echo "  This action builds the flatpak package"
            echo -e "\nOptions:\n"
            echo "  -h, -help: Display this help message"
            echo "  -u, --user: Build the flatpak package as the current user"
            echo "  -r, --run: Run the flatpak package after building"
            echo "  -c, --command [COMMAND]: Pass a command to the run action"
            echo "  -a, --args [ARGS]: Pass additional arguments to the run action"
            ;;
        RUN)
            echo "Usage: $0 ACTION [OPTIONS] [ARGS]"
            echo -e "\nHelp for run action:\n"
            echo "  This action runs the flatpak package"
            echo -e "\nOptions:\n"
            echo "  -h, --help: Display this help message"
            echo "  -u, --user: Run the flatpak package as the current user"
            echo "  -c, --command [COMMAND]: Pass a command to the run action"
            echo "  -a, --args [ARGS]: Pass additional arguments to the run action"
            ;;
        *)
            echo "Usage: $0 ACTION [OPTIONS]"
            echo -e "\nActions:\n"
            echo "  build: Build the flatpak package"
            echo "  run: Run the flatpak package"
            echo -e "\nOptions:\n"
            echo "  -h, --help: Display this help message"
            echo -e "\nYou can get help for a specific action by running: $0 ACTION -h|--help\n"
            ;;
    esac
    exit 0
}

# @description Parse command line arguments
# @arg $@ string Command line arguments
# @exitcode 0 If the arguments are parsed successfully
# @stdout: Usage if the command line arguments fail to parse
function parse_args() {
    if [ $# -eq 0 ]; then
        usage
    fi
    if [ $# -lt 1 ]; then
        error "No action provided"
        usage
    fi
    local action
    action="${1}"
    if [ "${action}" = "-h" ] || [ "${action}" = "--help" ]; then
        usage
    fi
    action=$(echo "${action}" | tr '[:lower:]' '[:upper:]')
    shift 1
    case "${action}" in
        BUILD)
            BUILD=true
            while [ $# -gt 0 ]; do
                if [ "$AARGS" = true ]; then
                    BARGS+=("$1")
                else
                    case "$1" in
                        -h|--help)
                            usage "BUILD"
                            ;;
                        -r|--run)
                            RUN=true
                            ;;
                        -u|--user)
                            USERMODE=true
                            ;;
                        -c|--command)
                            COMMAND="$2"
                            shift 1
                            ;;
                        -a|--args)
                            AARGS=true
                            ;;
                        *)
                            error "Invalid argument: $1"
                            usage "BUILD"
                            ;;
                    esac
                fi
                shift 1
            done
            ;;
        RUN)
            RUN=true
            while [ $# -gt 0 ]; do
                if [ "$AARGS" = true ]; then
                    BARGS+=("$1")
                else
                    case "$1" in
                        -h|--help)
                            usage "RUN"
                            ;;
                        -r|--run)
                            RUN=true
                            ;;
                        -u|--user)
                            USERMODE=true
                            ;;
                        -c|--command)
                            COMMAND="$2"
                            shift 1
                            ;;
                        -a | --args)
                            AARGS=true
                            ;;
                        *)
                            error "Invalid argument: $1"
                            usage "RUN"
                            ;;
                    esac
                fi
                shift 1
            done
            ;;
        *)
            error "Invalid action: ${action}"
            usage
            ;;
    esac
}

# @description Get the user mode flag
# @exitcode 0
# @stdout User mode flag
function __user_mode() {
    if [ "${USERMODE}" = true ]; then
        echo -ne "--user "
    fi
}

# @description Get the passed-through command line arguments
# @exitcode 0
# @stdout Command line arguments
function __bargs() {
     if [ ${#BARGS[@]} -gt 0 ]; then
         echo -ne " ${BARGS[*]}"
     fi
}

# @description Get the passed-through command
# @exitcode 0
# @stdout Command
function __command() {
    if [ -n "${COMMAND}" ]; then
        echo -ne "--command=${COMMAND} "
    fi
}

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
    # shellcheck disable=SC2046
    if ! exec_flatpak $(__user_mode)remote-list | grep -qi "${repository}"; then
        warning "Flatpak repository ${repository} does not exist"
        return 1
    fi
    # shellcheck disable=SC2046
    if ! exec_flatpak $(__user_mode)remote-list | grep -qi "${uri}"; then
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
    # shellcheck disable=SC2046
    if ! exec_flatpak $(__user_mode)list | grep -qi "${package}"; then
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
    # shellcheck disable=SC2046
    if ! exec_flatpak $(__user_mode)remote-add --if-not-exists ${repository} ${uri}; then
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
    # shellcheck disable=SC2046
    if ! exec_flatpak install $(__user_mode)flathub "${package}" -y; then
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
    # shellcheck disable=SC2046
    if ! exec_flatpak run org.flatpak.Builder --install --install-deps-from=flathub --default-branch=master --force-clean $(__user_mode) build-dir ${package_config}; then
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
    # shellcheck disable=SC2046
    if ! exec_flatpak run $(__command)$(__user_mode)"${package_name}"$(__bargs); then
        err "Failed to test-run flatpak package"
        return 1
    else
        success "Flatpak package ran successfully"
        return 0
    fi
}

parse_args "$@"
if [ "${BUILD}" = true ]; then
    build_flatpak "com.usebottles.bottles.yml"
fi
if [ "${RUN}" = true ]; then
    run_flatpak "com.usebottles.bottles"
fi
