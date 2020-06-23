args=commandArgs(trailing=T)
if(len(args)!=1) {
    cat("\n    usage: makeRNASeqProject.R limsRequestFile\n\n")
    quit()
}

source("/home/socci/Code/LIMS/LimsETL/tools.R")

require(yaml)
require(tidyverse)

rFile=args[1]

request=read_yaml(rFile)
mapping=read_tsv(gsub("metadata.yaml","sample_mapping.txt",rFile),col_names=F,col_types=cols())

requestRNA=list(

    ProjectID=cc("Proj",request$requestId),
    Run_Pipeline="rnaseq",
    Institution="bic",
    RunNumber="1",
    NumberOfSamples=mapping %>% distinct(X2) %>% nrow,

    LIMS_Strand = request$strand,
    Strand="Reverse,None",

    Species = request$Species,

    PI_Name = normalizeName(request$labHeadName),
    PI = gsub("@.*$","",request$labHeadEmail),
    "PI_E-mail" = request$labHeadEmail,

    Investigator_Name = normalizeName(request$investigatorName),
    Investigator = gsub("@.*$","",request$investigatorEmail),
    "Investigator_E-mail" = request$investigatorEmail,

    ProjectFolder=file.path("/ifs/projects/BIC/rnaseq",request$requestId),
    DeliverTo_Name=request$investigatorName,
    DeliverTo_Email=request$investigatorEmail,

    Pipelines="NULL, RNASEQ_STANDARD_GENE_V1, RNASEQ_DIFFERENTIAL_GENE_V1",

    `Charges-CCFN`=""

    )


yy=as.yaml(requestRNA)
yy=gsub("'","",yy)
write(yy,"_request")

