"""This file originated from Lutris (https://github.com/lutris/lutris/blob/master/lutris/util/nvidia.py)"""
"""Nvidia library detection from Proton"""

import os
from ctypes import CDLL, POINTER, Structure, addressof, c_char_p, c_int, c_void_p, cast

from bottles.backend.logger import Logger

logging = Logger()

RTLD_DI_LINKMAP = 2


class LinkMap(Structure):
    """
    from dlinfo(3)

    struct link_map {
        ElfW(Addr) l_addr;  /* Difference between the
                               address in the ELF file and
                               the address in memory */
        char      *l_name;  /* Absolute pathname where
                               object was found */
        ElfW(Dyn) *l_ld;    /* Dynamic section of the
                               shared object */
        struct link_map *l_next, *l_prev;
                            /* Chain of loaded objects */
        /* Plus additional fields private to the implementation */
    };
    """
    _fields_ = [("l_addr", c_void_p), ("l_name", c_char_p), ("l_ld", c_void_p)]


def get_nvidia_glx_path():
    """Return the absolute path to the libGLX_nvidia library"""
    try:
        libdl = CDLL("libdl.so.2")
    except OSError:
        logging.error("Unable to load libdl.so.2")
        return None

    try:
        libglx_nvidia = CDLL("libGLX_nvidia.so.0")
    except OSError:
        logging.error("Unable to load libGLX_nvidia.so.0")
        return None

    # from dlinfo(3)
    #
    # int dlinfo (void *restrict handle, int request, void *restrict info)
    dlinfo_func = libdl.dlinfo
    dlinfo_func.argtypes = c_void_p, c_int, c_void_p
    dlinfo_func.restype = c_int

    # Allocate a LinkMap object
    glx_nvidia_info_ptr = POINTER(LinkMap)()

    # Run dlinfo(3) on the handle to libGLX_nvidia.so.0, storing results at the
    # address represented by glx_nvidia_info_ptr
    if (
        dlinfo_func(
            libglx_nvidia._handle, RTLD_DI_LINKMAP, addressof(glx_nvidia_info_ptr)
        ) != 0
    ):
        logging.error("Unable to read Nvidia information")
        return None

    # Grab the contents our of our pointer
    glx_nvidia_info = cast(glx_nvidia_info_ptr, POINTER(LinkMap)).contents

    # Decode the path to our library to a str()
    if glx_nvidia_info.l_name is None:
        logging.error("Error reading the Nvidia library path")
        return None
    try:
        libglx_nvidia_path = os.fsdecode(glx_nvidia_info.l_name)
    except UnicodeDecodeError as ex:
        logging.error("Error decoding the Nvidia library path: %s", ex)
        return None

    # Follow any symlinks to the actual file
    return os.path.realpath(libglx_nvidia_path)


def get_nvidia_dll_path():
    """Return the path to the location of DLL files for use by Wine/Proton
    from the NVIDIA Linux driver.
    See https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/issues/71 for
    background on the chosen method of DLL discovery.
    """
    from bottles.backend.utils.gpu import GPUUtils, GPUVendors
    if not GPUUtils.is_gpu(GPUVendors.NVIDIA): return None

    libglx_path = get_nvidia_glx_path()
    if not libglx_path:
        logging.warning("Unable to locate libGLX_nvidia")
        return None
    nvidia_wine_dir = os.path.join(os.path.dirname(libglx_path), "nvidia/wine")
    if os.path.exists(os.path.join(nvidia_wine_dir, "nvngx.dll")):
        return nvidia_wine_dir
    return None
