#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2016 Olaf Lessenich <lessenic@fim.uni-passau.de>
#
# Distributed under terms of the MIT license.

"""
This is a simple wrapper to deploy required resources and submit slurm jobs.
It reads a config file that is supplied as command line argument,
retrieves specified tools and input files, and generates an sbatch script, that
is automatically submitted to slurm.
"""

import imp
import os
import sys
import logging
import json
import argparse

try:
    imp.find_module("plumbum")
except ImportError:
    print("Please install plumbum", file=sys.stderr)
    print("https://plumbum.readthedocs.org/en/latest/", file=sys.stderr)
    sys.exit()


gitdir = ".git"


def print_help(cmd):
    print("Usage: %s <config>" % cmd, file=sys.stderr)
    sys.exit(1)


def install_dependencies(tool):
    for dep in tool.get("pip_dependencies", []):
        from plumbum.cmd import pip3
        pip3["install", dep]()


def setup_tool(tool, installdir, bindir):
    """
    Checkout specified branch or tag, run build command and create symlinks
    to executables.
    """
    assert os.path.isdir(bindir), "Bin directory not found: %s!" % bindir
    logging.info("Preparing %s: git checkout %s" % (tool["name"],
                                                    tool["version"]))

    from plumbum import local
    from plumbum.cmd import git
    with local.cwd(installdir):
        if tool.get("version", None):
            git["checkout", tool["version"]]()
        if tool.get("build", None):
            build = local[tool["build"][0]]
            build[tool["build"][1:]]()

    for tool_file in tool.get("install", []):
        source = os.path.join(installdir, tool_file["source"])
        target = os.path.join(bindir, tool_file["target"])
        assert os.path.isfile(source), \
            "Executable does not exist: %s!" % source

        if os.path.islink(target):
            os.unlink(target)

        from plumbum.cmd import ln
        ln["-s", source, target]()


def install_tool(tool, installdir):
    logging.info("Preparing %s: git clone %s %s" % (tool["name"],
                                                    tool["repository"],
                                                    installdir))

    from plumbum.cmd import git
    git["clone", "-q", tool["repository"], installdir]()


def update_tool(tool, installdir):
    logging.info("Preparing %s: git pull" % tool["name"])

    from plumbum import local
    from plumbum.cmd import git
    with local.cwd(installdir):
        git["pull", "-q"]()


def prepare_input_files(inputfiles, inputdir):
    assert os.path.isdir(inputdir), "Input directory not found: %s!" % inputdir

    from plumbum.cmd import rm, wget, git

    for f in inputfiles:
        logging.info("Preparing input file: %s" % f["target"])
        target = os.path.join(inputdir, f["target"])

        if os.path.exists(target):
            logging.info("Target exists: %s" % target)
            logging.info("Removing %s" % target)
            rm["-r", target]()

        if f["type"] == "http":
            wget["-q", "-O" + target, f["source"]]()
        elif f["type"] == "git":
            git["clone", "-q", f["source"], target]()
        else:
            raise Exception("Type of input resource unknown!")


def prepare_tools(tools, tooldir, bindir):
    assert os.path.isdir(tooldir), "Tool directory not found: %s!" % tooldir

    for tool in tools:
        installdir = os.path.join(tooldir, tool["name"])
        logging.info("Preparing tool: %s (%s)" % (tool["name"], installdir))

        install_dependencies(tool)
        if os.path.isdir(os.path.join(installdir, gitdir)):
            update_tool(tool, installdir)
        else:
            install_tool(tool, installdir)
        setup_tool(tool, installdir, bindir)


def prepare(config):
    """
    Prepares environment for the job, including input files, required tools,
    and output directories.
    Returns working directory for the job.
    """

    logging.info("Preparing job \"%s\"" % config["name"])
    inputdir = os.path.join(config["inputdir"], config["name"])
    tooldir = config["tooldir"]

    if not os.path.exists(inputdir):
        os.mkdir(inputdir)

    prepare_input_files(config.get("input", []), inputdir)
    prepare_tools(config.get("tools", []), tooldir, config["bindir"])

    return inputdir


def submit(config, workdir, dry_run):
    """
    Submits a job using sbatch.
    """

    logging.info("Submitting job \"%s\":" % config["name"])

    for tool in config["tools"]:
        if tool["name"] == config["executable"]:
            cmd = tool["run"]

    if cmd:
        from plumbum import local
        with local.cwd(workdir):
            # prepend executable path with local bindir
            local.env.path.insert(0, config["bindir"])

            output = os.path.join(config["outputdir"], config["name"])
            if not os.path.isdir(output):
                os.mkdir(output)

            outfile = os.path.join(output, "%j.out")
            errfile = os.path.join(output, "%j.err")
            outdir = os.path.join(output, "out")
            if not os.path.isdir(outdir):
                os.mkdir(outdir)

            cmd_args = ' '.join(config["args"]).replace("$$OUT$$", outdir)

            batchfile = []
            batchfile.append('#!/bin/bash')
            batchfile.append('#SBATCH -J %s' % config["name"])
            batchfile.append('#SBATCH -p %s' % config["partition"])
            batchfile.append('#SBATCH -A %s' % config["account"])
            batchfile.append('#SBATCH -o %s' % outfile)
            batchfile.append('#SBATCH -e %s' % errfile)
            batchfile.append("%s %s" % (cmd, cmd_args))

            job = "\n".join(batchfile)
            sep = 80 * "-"
            print("\n".join((sep, job, sep)))

            if not dry_run:
                sbatch = local["sbatch"]
                (sbatch << job)()
            else:
                logging.info("Dry run: not submitting job.")
    else:
        raise Exception("No executable command found!")


def main():
    """
    Executes a slurm job based on a specified config.
    """

    global logging

    logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("-n",
                        "--dry-run",
                        help="perform a trial run with no changes made",
                        action="store_true")
    parser.add_argument("config_files", default=[], nargs="+")
    args = parser.parse_args()

    for config_file in args.config_files:
        with open(config_file, "r") as configuration:
            logging.info("Using config file: %s" % config_file)
            config = json.load(configuration)

        workdir = prepare(config)
        submit(config, workdir, args.dry_run)


if __name__ == "__main__":
    main()
