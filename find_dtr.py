import os,sys
from Bio import SeqIO,Seq
from Bio.SeqRecord import SeqRecord
import pandas as pd
import argparse
from tqdm import tqdm
import shutil

def parse_args():
    # Create argument parser
    parser = argparse.ArgumentParser()

    # Positional mandatory arguments
    parser.add_argument("fasta", help="Fasta file containing the sequences to check for presence of DTR", type=str)

    # Optional arguments
    parser.add_argument("-p", "--prefix", help="Output file prefix (for <prefix>.dtr.stats.tsv and <prefix>.dtr.fasta) [output]", type=str, default="output")
    parser.add_argument("-o", "--overlap", help="Check for overlaps between the first and last <overlap> percent of the sequence [20]", type=int, default=20)
    parser.add_argument("-t", "--tmpdir", help="Path to tmp directory where nucmer alignment data is written [./nuc_tmp]", type=str, default="nuc_tmp")

    # Parse arguments
    args = parser.parse_args()

    return args

def subseq_read_and_run_nucmer(seq_entry, args):
    prefix    = os.path.join(args.tmpdir,seq_entry.id)
    read_len  = len(seq_entry.seq)

    ovlp_len = int((args.overlap/100)*read_len)

    seq_start = seq_entry.seq[:ovlp_len]
    record    = SeqRecord(seq=seq_start, id=seq_entry.id+".first{}".format(ovlp_len), description=seq_entry.id+".first{}".format(ovlp_len))
    start_fn  = prefix+".first{}.fa".format(ovlp_len)
    SeqIO.write(record, start_fn, "fasta")

    seq_end   = seq_entry.seq[-ovlp_len:]
    record    = SeqRecord(seq=seq_end, id=seq_entry.id+".last{}".format(ovlp_len), description=seq_entry.id+".last{}".format(ovlp_len))
    end_fn    = prefix+".last{}.fa".format(ovlp_len)
    SeqIO.write(record, end_fn, "fasta")

    nucmer_out = "%s.out" % seq_entry.id.split("|")[0]
    nucmer_CMD = "nucmer -p %s -c 10 %s %s > /dev/null 2>&1" % (prefix, start_fn, end_fn)
    os.system(nucmer_CMD)
    delta      = "{}.delta".format(prefix)

    coords     = "{}.coords".format(prefix)
    sc_CMD     = "show-coords -T -l {} > {}".format(delta, coords)
    os.system(sc_CMD)

    os.remove(start_fn)
    os.remove(end_fn)
    os.remove(delta)

    return coords,ovlp_len

def write_dtr_stats(stats, args):
    df    = pd.DataFrame.from_dict(stats)
    fname = "{}.dtr.stats.tsv".format(args.prefix)
    print("Writing {}".format(fname))
    df.to_csv(fname, sep="\t", index=False)

def write_dtr_fasta(dtr_seqs, args):
    fname = "{}.dtr.fasta".format(args.prefix)
    print("Writing {}".format(fname))
    SeqIO.write(dtr_seqs, fname, "fasta")

def main(args):
    os.makedirs(args.tmpdir, exist_ok=True)

    stats = {"seq_id": [],     \
             "seq_len": [],    \
             "has_dtr": [],    \
             "dtr_length": [], \
             "dtr_start": [],  \
             "dtr_end": []}

    dtr_seqs = []

    print("Searching for DTR in {} sequences".format(len([S for S in SeqIO.parse(args.fasta, "fasta")])))

    for seq_entry in tqdm(SeqIO.parse(args.fasta, "fasta")):
        coords,ovlp_len = subseq_read_and_run_nucmer(seq_entry, args)
        df = pd.read_csv(coords, sep="\t", skiprows=4, names=["s1","e1","s2","e2","len1","len2", \
                                                              "idy","covr","covq","readr","readq"])
        
        if df.shape[0]>0: # an alignment exists
            # get the sum of self-self alignments and see if those alignment
            # extend all the way to the beginning and end of the sequence.
            dtr       = True
            aln_sum   = df.loc[:,"len1"].sum()
            aln_start = min(df.loc[:,"s1"])
            aln_end   = max(df.loc[:,"e2"])

            # transform the aln_end value to reflect num. bases before end of genome/read
            aln_end   = aln_end - ovlp_len

            # If the alignments are too far from the end of the read, don't call it a DTR
            if aln_start>200 or aln_end<-200:
                dtr = False
        else: # no alignment exists
            dtr       = False
            aln_sum   = 0
            aln_start = -1
            aln_end   = 1

        os.remove(coords)

        stats["seq_id"].append(seq_entry.id)
        stats["seq_len"].append(len(seq_entry.seq))
        stats["has_dtr"].append(dtr)
        stats["dtr_length"].append(aln_sum)
        stats["dtr_start"].append(aln_start)
        stats["dtr_end"].append(aln_end)

        if dtr:
            dtr_seqs.append(seq_entry)

    shutil.rmtree(args.tmpdir)

    write_dtr_stats(stats, args)
    write_dtr_fasta(dtr_seqs, args)

if __name__=="__main__":
    args = parse_args()

    main(args)
