# vkbasalt.py: library supplying the logics and functions to generate configs
#
# Copyright 2022 vkbasalt-cli Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from os import path, environ, system, remove
from sys import exit
from shutil import copyfile
import configparser
import logging


def parse(args, *arguments):
    # Apply default settings if possible
    if args.default:
        install_paths = [
            "/usr/lib/extensions/vulkan/vkBasalt/etc/vkBasalt",
            "/usr/local",
            "/usr/share/vkBasalt",
        ]
        for item in install_paths:
            file_path = path.join(item, "vkBasalt.conf")
            if path.isfile(file_path):
                if args.output:
                    logging.info(f"Outputting file to {file_path}")
                    copyfile(file_path, path.join(args.output, "vkBasalt.conf"))
                if args.exec:
                    environ["ENABLE_VKBASALT"] = "1"
                    environ["VKBASALT_CONFIG_FILE"] = file_path
                    system(f"{args.exec}")
                return
        logging.error(f"No such path for vkBasalt exists")
        exit(1)

    # Generate config and check for errors
    if args.effects or args.lut_file_path:
        file = []

        # --disable-on-launch
        file.append("enableOnLaunch = ")
        if args.disable_on_launch:
            logging.info("Setting Key enableOnLaunch = False")
            file.append("False\n")
        else:
            logging.info("Setting Key enableOnLaunch = True")
            file.append("True\n")

        # --toggle-key
        file.append("toggleKey = ")
        if args.toggle_key:
            file.append(f"{args.toggle_key[0]}\n")
        else:
            file.append("Home\n")

        # --cas-sharpness
        if args.cas_sharpness:
            args.cas_sharpness = round(args.cas_sharpness, 2)
            if -1 <= args.cas_sharpness <= 1:
                logging.info(f"Setting Key casSharpness = {args.cas_sharpness}")
                file.append(f"casSharpness = {args.cas_sharpness}\n")
            else:
                logging.error(f"Error: CAS sharpness must be above -1 and below 1")
                exit(1)

        # --dls-sharpness
        if args.dls_sharpness:
            args.dls_sharpness = round(args.dls_sharpness, 2)
            if 0 <= args.dls_sharpness <= 1:
                logging.info(f"Setting Key dlsSharpness = {args.dls_sharpness}")
                file.append(f"dlsSharpness = {args.dls_sharpness}\n")
            else:
                logging.error(f"Error: DLS sharpness must be above 0 and below 1")
                exit(1)

        # --dls-denoise
        if args.dls_denoise:
            args.dls_denoise = round(args.dls_denoise, 2)
            if 0 <= args.dls_denoise <= 1:
                logging.info(f"Setting Key dlsDenoise = {args.dls_denoise}")
                file.append(f"dlsDenoise = {args.dls_denoise}\n")
            else:
                logging.error(f"Error: DLS denoise must be above 0 and below 1")
                exit(1)

        # --fxaa-subpixel-quality
        if args.fxaa_subpixel_quality:
            args.fxaa_subpixel_quality = round(args.fxaa_subpixel_quality, 2)
            if 0 <= args.fxaa_subpixel_quality <= 1:
                logging.info(f"Setting Key fxaaQualitySubpix = {args.fxaa_subpixel_quality}")
                file.append(f"fxaaQualitySubpix = {args.fxaa_subpixel_quality}\n")
            else:
                logging.error(f"Error: FXAA subpixel quality must be above 0 and below 1")
                exit(1)

        # --fxaa-edge-quality-threshold
        if args.fxaa_quality_edge_threshold:
            args.fxaa_quality_edge_threshold = round(args.fxaa_quality_edge_threshold, 2)
            if 0 <= args.fxaa_quality_edge_threshold <= 1:
                logging.info(f"Setting Key fxaaQualityEdgeThreshold = {args.fxaa_quality_edge_threshold}")
                file.append(f"fxaaQualityEdgeThreshold = {args.fxaa_quality_edge_threshold}\n")
            else:
                logging.error(f"Error: FXAA edge quality threshold must be above 0 and below 1")
                exit(1)

        # --fxaa-quality-edge-threshold-min
        if args.fxaa_quality_edge_threshold_min:
            args.fxaa_quality_edge_threshold_min = round(args.fxaa_quality_edge_threshold_min, 3)
            if 0 <= args.fxaa_quality_edge_threshold_min <= 0.1:
                logging.info(f"Setting Key fxaaQualityEdgeThresholdMin = {args.fxaa_quality_edge_threshold_min}")
                file.append(f"fxaaQualityEdgeThresholdMin = {args.fxaa_quality_edge_threshold_min}\n")
            else:
                logging.error(f"Error: FXAA edge quality threshold minimum must be above 0 and below 0.1")
                exit(1)

        # --smaa-edge-detection
        if args.smaa_edge_detection:
            logging.info(f"Setting Key smaaEdgeDetection = {args.smaa_edge_detection}")
            file.append(f"smaaEdgeDetection = {args.smaa_edge_detection}\n")

        # --smaa-threshold
        if args.smaa_threshold:
            args.smaa_threshold = round(args.smaa_threshold, 3)
            if 0 <= args.smaa_threshold <= 0.5:
                logging.info(f"Setting Key smaaThreshold = {args.smaa_threshold}")
                file.append(f"smaaThreshold = {args.smaa_threshold}\n")
            else:
                logging.error(f"Error: SMAA threshold must be above 0 and below 0.5")
                exit(1)

        # --smaa-max-search-steps
        if args.smaa_max_search_steps:
            args.smaa_max_search_steps = round(args.smaa_max_search_steps)
            if 0 <= args.smaa_max_search_steps <= 112:
                logging.info(f"Setting Key smaaMaxSearchSteps = {args.smaa_max_search_steps}")
                file.append(f"smaaMaxSearchSteps = {args.smaa_max_search_steps}\n")
            else:
                logging.error(f"Error: SMAA max search steps must be above 0 and below 112")
                exit(1)

        # --smaa-max-search-steps-diagonal
        if args.smaa_max_search_steps_diagonal:
            args.smaa_max_search_steps_diagonal = round(args.smaa_max_search_steps_diagonal)
            if 0 <= args.smaa_max_search_steps_diagonal <= 20:
                logging.info(f"Setting Key smaaMaxSearchStepsDiag = {args.smaa_max_search_steps_diagonal}")
                file.append(f"smaaMaxSearchStepsDiag = {args.smaa_max_search_steps_diagonal}\n")
            else:
                logging.error(f"Error: SMAA max search steps diagonal must be above 0 and below 20")
                exit(1)

        # --smaa-corner-rounding
        if args.smaa_corner_rounding:
            args.smaa_corner_rounding = round(args.smaa_corner_rounding)
            if 0 <= args.smaa_corner_rounding <= 100:
                logging.info(f"Setting Key smaaCornerRounding = {args.smaa_corner_rounding}")
                file.append(f"smaaCornerRounding = {args.smaa_corner_rounding}\n")
            else:
                logging.error(f"Error: SMAA corner rounding must be above 0 and below 100")
                exit(1)

        # --lut-file-path
        if args.lut_file_path:
            if not " " in args.lut_file_path:
                logging.info(f"Setting Key lutFile = {args.lut_file_path}")
                file.append(f"lutFile = {args.lut_file_path}\n")
            else:
                logging.error("Error: CLUT must not contain any whitespace")
                exit(1)

        # Output file
        if args.output:
            if path.isdir(args.output):
                vkbasalt_conf = path.join(args.output, "vkBasalt.conf")
            else:
                logging.error(f"Error: No such directory")
                exit(1)
        else:
            vkbasalt_conf = "/tmp/vkBasalt.conf"
            tmp = True

        # Write and close file
        with open(vkbasalt_conf, "w") as f:
            if args.effects:
                args.effects = ':'.join(args.effects)
                logging.info(f"Setting Key effects = {args.effects}")
                file.append(f"effects = {args.effects}\n")
            logging.info(f"Writing to: {vkbasalt_conf}")
            f.write("".join(file))

        # --exec
        if args.exec:
            environ["ENABLE_VKBASALT"] = "1"
            environ["VKBASALT_CONFIG_FILE"] = vkbasalt_conf
            system(f"{args.exec}")

            if tmp:
                remove(vkbasalt_conf)

    else:
        logging.error(f"Please specify one or more effects, or a CLUT file path.")
        exit(1)

def getConfigValue(config, value):
    with open(config, "r") as f:
        file = "[config]\n"+f.read()
        config = configparser.ConfigParser(allow_no_value=True)
        config.read_string(file)
        return config['config'].get(value)

def ParseConfig(config):
    class Args:
        default = False
        effects = False
        output = False
        disable_on_launch = False
        toggle_key = False
        cas_sharpness = False
        dls_sharpness = False
        dls_denoise = False
        fxaa_subpixel_quality = False
        fxaa_quality_edge_threshold = False
        fxaa_quality_edge_threshold_min = False
        smaa_edge_detection = False
        smaa_threshold = False
        smaa_max_search_steps = False
        smaa_max_search_steps_diagonal = False
        smaa_corner_rounding = False
        lut_file_path = False
    Args.effects = getConfigValue(config, 'effects')
    Args.toggle_key = getConfigValue(config, 'toggleKey')
    Args.disable_on_launch = "True" if getConfigValue(config, 'enableOnLaunch') == "False" else "False"
    Args.cas_sharpness = getConfigValue(config, 'casSharpness')
    Args.dls_sharpness = getConfigValue(config, 'dlsSharpness')
    Args.dls_denoise = getConfigValue(config, 'dlsDenoise')
    Args.fxaa_subpixel_quality = getConfigValue(config, 'fxaaQualitySubpix')
    Args.fxaa_quality_edge_threshold = getConfigValue(config, 'fxaaQualityEdgeThreshold')
    Args.fxaa_quality_edge_threshold_min = getConfigValue(config, 'fxaaQualityEdgeThresholdMin')
    Args.smaa_edge_detection = getConfigValue(config, 'smaaEdgeDetection')
    Args.smaa_threshold = getConfigValue(config, 'smaaThreshold')
    Args.smaa_max_search_steps = getConfigValue(config, 'smaaMaxSearchSteps')
    Args.smaa_max_search_steps_diagonal = getConfigValue(config, 'smaaMaxSearchStepsDiag')
    Args.smaa_corner_rounding = getConfigValue(config, 'smaaCornerRounding')
    Args.lut_file_path = getConfigValue(config, 'lutFile')

    return(Args)

