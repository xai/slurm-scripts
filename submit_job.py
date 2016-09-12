#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2016 Olaf Lessenich <lessenic@fim.uni-passau.de>
#
# Distributed under terms of the MIT license.

"""

"""

import imp
import os
import sys
import logging
import socket
import json

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


def setup_tool(tool, installdir):
    logging.info("Preparing %s: git checkout %s" % (tool["name"],
                                                    tool["version"]))

    from plumbum import local
    from plumbum.cmd import git
    with local.cwd(installdir):
        git["checkout", tool["version"]]()


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

    from plumbum.cmd import wget

    for f in inputfiles:
        logging.info("Preparing input file: %s" % f["target"])
        target = os.path.join(inputdir, f["target"])
        wget["-q", "-O" + target, f["source"]]()


def prepare_tools(tools, tooldir):
    assert os.path.isdir(tooldir), "Tool directory not found: %s!" % tooldir

    for tool in tools:
        installdir = os.path.join(tooldir, tool["localpath"])
        logging.info("Preparing tool: %s (%s)" % (tool["name"], installdir))
        if os.path.isdir(os.path.join(installdir, gitdir)):
            update_tool(tool, installdir)
        else:
            install_tool(tool, installdir)
        setup_tool(tool, installdir)


def prepare(config):
    """
    Prepares environment for the job, including input files, required tools,
    and output directories.
    """

    logging.info("Preparing job \"%s\" as id %s on %s" % (config["name"],
                                                          jobid,
                                                          hostname))
    inputdir = os.path.join(config["inputdir"], jobid)
    tooldir = config["tooldir"]

    if not os.path.exists(inputdir):
        os.mkdir(inputdir)

    prepare_input_files(config["input"], inputdir)
    prepare_tools(config["tools"], tooldir)


def main():
    """
    Executes a slurm job based on a specified config
    """
    global jobid, hostname, logging

    """ read environment variables """
    jobid = os.getenv("SLURM_JOB_ID", "unknown")
    hostname = socket.gethostname()

    logprefix = "%s:%s:" % (jobid, hostname)
    logging.basicConfig(format=logprefix + "%(levelname)s:%(message)s",
                        level=logging.INFO)

    if len(sys.argv) == 1:
        print_help(sys.argv[0])

    with open(sys.argv[1], "r") as configuration:
        logging.info("Using config file: %s" % sys.argv[1])
        config = json.load(configuration)

    prepare(config)


if __name__ == "__main__":
    main()
