#!/bin/sh
#
# queue.sh
# Copyright (C) 2016 Olaf Lessenich <lessenic@fim.uni-passau.de>
#
# Distributed under terms of the MIT license.
#

#SBATCH -e /home/lessenic/deploy/output/slurm-%j.out
#SBATCH -o /home/lessenic/deploy/output/slurm-%j.out
#SBATCH -A anywhere
#SBATCH -p anywhere
#SBATCH -N 1-1
#SBATCH --exclusive
#SBATCH --constraint=zeus

set -eu

srun $@
