"""Next-gen alignments with TopHat a spliced read mapper for RNA-seq experiments.

http://tophat.cbcb.umd.edu
"""
import os
import subprocess
from contextlib import closing

import pysam
import numpy

from bcbio.ngsalign import bowtie
from bcbio.utils import safe_makedir, file_transaction

galaxy_location_file = "bowtie_indices.loc"

_out_fnames = ["accepted_hits.sam", "junctions.bed", "insertions.bed", "deletions.bed"]

def align(fastq_file, pair_file, ref_file, out_base, align_dir, config):
    qual_format = config["algorithm"].get("quality_format", None)
    if qual_format is None or qual_format.lower() == "illumina":
        qual_flags = ["--solexa1.3-quals"]
    else:
        qual_flags = []
    out_dir = os.path.join(align_dir, "%s_tophat" % out_base)
    safe_makedir(out_dir)
    out_file = os.path.join(out_dir, _out_fnames[0])
    files = [ref_file, fastq_file]
    if not os.path.exists(out_file):
        cl = [config["program"].get("tophat", "tophat")]
        cl += qual_flags
        cl += ["-m", str(config["algorithm"].get("max_errors", 0)),
               "--output-dir", out_dir,
               "--no-convert-bam"]
        if pair_file:
            d, d_stdev = _estimate_paired_innerdist(fastq_file, pair_file, ref_file,
                                                    out_base, out_dir, config)
            cl += ["--mate-inner-dist", str(d),
                   "--mate-std-dev", str(d_stdev)]
            files.append(pair_file)
        cl += files
        with file_transaction([os.path.join(out_dir, f) for f in _out_fnames]):
            child = subprocess.check_call(cl)
    out_file_final = os.path.join(out_dir, "%s.sam" % out_base)
    os.symlink(out_file, out_file_final)
    return out_file_final

def _estimate_paired_innerdist(fastq_file, pair_file, ref_file, out_base,
                               out_dir, config):
    """Use Bowtie to estimate the inner distance of paired reads.
    """
    work_dir = os.path.join(out_dir, "innerdist_estimate")
    safe_makedir(work_dir)
    extra_args = ["-s", "1000000", "-u", "250000"]
    out_sam = bowtie.align(fastq_file, pair_file, ref_file, out_base,
                           work_dir, config, extra_args)
    dists = []
    with closing(pysam.Samfile(out_sam)) as work_sam:
        for read in work_sam:
            if not read.is_unmapped and read.is_read1:
                dists.append(abs(read.isize) - 2 * read.rlen)
    return int(round(numpy.mean(dists))), int(round(numpy.std(dists)))
