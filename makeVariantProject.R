args=commandArgs(trailing=T)
if(len(args)!=1) {
    cat("\n    usage: makeVariantProject.R limsMetaDataFile.yaml\n\n")
    quit()
}

source("/home/socci/Code/LIMS/LimsETL/tools.R")

suppressPackageStartupMessages({
    require(yaml);
    require(tidyverse);
})

rFile=args[1]

request=read_yaml(rFile)
mapping=read_tsv(gsub("metadata.yaml","sample_mapping.txt",rFile),col_names=F,col_types=cols())

if(grepl(";",request$baitsUsed)) {
    cat("\n")
    cat("   Multiple baitSets used; need to resolve manually\n\n")
    cat("      ",request$baitsUsed,"\n")
    cat("\n")
    stop("FATAL ERROR")
}

knownAssayPaths=scan("/home/socci/Code/LIMS/LimsETL/knownTargets","")
names(knownAssayPaths)=basename(knownAssayPaths)

assay=gsub("_baits$","",request$baitsUsed,ignore.case=T)

assayTranslations=c(
    "HemeBrainPACT_v1"="BRAINPACT_V1_b37",
    "mm_IMPACT_v1_mm10"="M-IMPACT_v1_mm10",
    "M-IMPACT_v2"="M-IMPACT_v2_mm10"
)

if(assay %in% names(assayTranslations)) {
    assay=assayTranslations[assay]
}

assayPath=knownAssayPaths[assay]

if(is.na(assayPath)) {
    cat("\n")
    cat("   Unknown assay; need to resolve manually\n\n")
    cat("      ",assay,"<>",request$baitsUsed,"\n")
    cat("\n")
    stop("FATAL ERROR")
}


requestVar=list(
    ProjectID=cc("Proj",request$requestId),

    Pipelines="variants",
    Run_Pipeline="variants",

    Institution="bic",
    RunNumber="1",
    NumberOfSamples=mapping %>% distinct(X2) %>% nrow,

    Species = request$Species,

    Assay = assay,
    AssayPath = assayPath,

    PI_Name = normalizeName(request$labHeadName),
    PI = gsub("@.*$","",request$labHeadEmail),
    "PI_E-mail" = request$labHeadEmail,

    Investigator_Name = normalizeName(request$investigatorName),
    Investigator = gsub("@.*$","",request$investigatorEmail),
    "Investigator_E-mail" = request$investigatorEmail,

    ProjectFolder=file.path("/juno/projects/BIC/variant",request$requestId),

    `Charges-CCFN`="",
    `Charges-Division`="BIC",
    `Charges-ProjectNumber`=request$requestId,
    `Charges-Qty`=mapping %>% distinct(X2) %>% nrow,
    `Charges-Service`="NG-M-IMPACT-02|WES-Human-BICVariant|WES-Mouse-BICVariant"

    )


yy=as.yaml(requestVar)
yy=gsub("'","",yy)
write(yy,"_request")

