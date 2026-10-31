len <- function(x) {length(x)}
cc <- function(...) {paste(...,sep='_')}

args=commandArgs(trailing=T)
if(len(args)!=1) {
    cat("\n    usage: makeRNASeqProject.R limsRequestFile\n\n")
    quit()
}

source("/home/socci/Code/LIMS/LimsETL/tools.R")

suppressPackageStartupMessages({
    require(yaml);
    require(tidyverse);
    require(openxlsx);
})

rFile=args[1]


mapping=read_tsv(gsub("metadata.yaml","sample_mapping.txt",rFile),col_names=F,col_types=cols())

if(nrow(mapping)==0) {
    cat("\n")
    cat("    Mapping file is empty; no valid samples; maybe all marked igocomplete==FALSE\n")
    cat("\n")
    quit()
}

request=read_yaml(rFile)


requestRNA=list(

    ProjectID=cc("Proj",request$requestId),
    Run_Pipeline="rnaseq",
    Institution="bic",
    RunNumber="1",
    NumberOfSamples=mapping %>% distinct(X2) %>% nrow,

    Recipe=request$recipe,

    LIMS_Strand = request$strand,
    #Strand="Reverse,None",
    Assay="na",
    AssayPath="na",

    Species = request$Species,

    PI_Name = normalizeName(request$labHeadName),
    PI = gsub("@.*$","",request$labHeadEmail),
    "PI_E-mail" = request$labHeadEmail,

    Investigator_Name = normalizeName(request$investigatorName),
    Investigator = gsub("@.*$","",request$investigatorEmail),
    "Investigator_E-mail" = request$investigatorEmail,

    ProjectFolder=file.path("/juno/projects/BIC/rnaseq",request$requestId),
    #DeliverTo_Name=request$investigatorName,
    #DeliverTo_Email=request$investigatorEmail,

    OtherContactEmails=request$otherContactEmails,

    Pipelines="NULL, RNASEQ_STANDARD_GENE_V1, RNASEQ_DIFFERENTIAL_GENE_V1",

    `Charges-CCFN`=""


    )


yy=as.yaml(requestRNA)
yy=gsub("'","",yy)
write(yy,"_request")

key=mapping %>%
    mutate(FASTQFileID=gsub(".*/Sample_","",X4)) %>%
    distinct(FASTQFileID) %>%
    mutate(InvestigatorSampleID=gsub("_IGO_.*","",FASTQFileID) %>% gsub("-","_",.)) %>%
    mutate(GroupName="")

write.xlsx(key,gsub("metadata.yaml","sample_key.xlsx",rFile))
write_tsv(select(key,-GroupName),gsub("metadata.yaml","sample_key.tsv",rFile))
