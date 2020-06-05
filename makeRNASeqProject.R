args=commandArgs(trailing=T)
if(len(args)!=1) {
    cat("\n    usage: makeRNASeqProject.R limsRequestFile\n\n")
    quit()
}

normalizeName<-function(nn) {

    pn=strsplit(nn," ")[[1]]
    paste0(pn[2],", ",pn[1])

}

require(yaml)
require(tidyverse)

rFile=args[1]

file.copy(rFile,paste0(rFile,".bak"))

request=read_yaml(rFile)

requestRNA=list(
    Run_Pipeline="rnaseq",
    Institution="bic",
    RunNumber="1",

    Strand = case_when(
                request$strand=="stranded-reverse" ~ "Reverse",
                request$strand=="None" ~ "None",
                T ~ "UNKOWN"
            ),

    Species = request$Species,

    PI_Name = normalizeName(request$labHeadName),
    PI = gsub("@.*$","",request$labHeadEmail),
    "PI_E-Mail" = request$labHeadEmail,

    Investigator_Name = normalizeName(request$investigatorName),
    Investigator = gsub("@.*$","",request$investigatorEmail),
    "Investigator_E-mail" = request$investigatorEmail,

    Pipelines="NULL, RNASEQ_STANDARD_GENE_V1, RNASEQ_DIFFERENTIAL_GENE_V1"
    )


yy=as.yaml(requestRNA)
yy=gsub("'","",yy)
write(yy,"testRequest.txt")

