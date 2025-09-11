#!/opt/common/CentOS_7/R/R-3.6.1/bin/Rscript --no-save

len<-function(x){length(x)}
cc <- function(...) {paste(...,sep='_')}

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
mappingFile=gsub("metadata.yaml","sample_mapping.txt",rFile)
mapping=read_tsv(mappingFile,col_names=F,col_types=cols())

if(grepl(";",request$baitsUsed)) {
    cat("\n")
    cat("   Multiple baitSets used; need to resolve manually\n\n")
    cat("      ",request$baitsUsed,"\n")
    cat("\n")
    stop("FATAL ERROR")
}

if(request$baitsUsed!="null") {

    knownAssayPaths=scan("/home/socci/Code/LIMS/LimsETL/knownTargets","")
    names(knownAssayPaths)=basename(knownAssayPaths)

    assay=gsub("_baits$","",request$baitsUsed,ignore.case=T)

    assayTranslations=c(
        "HemeBrainPACT_v1"="BRAINPACT_V1_b37",
        "mm_IMPACT_v1_mm10"="M-IMPACT_v1_mm10",
        "GRCm38_M-IMPACT_v1"="M-IMPACT_v1_mm10",
        "M-IMPACT_v2"="M-IMPACT_v2_mm10",
        "IDT_Exome_v2_GRCh38"="IDT_Exome_v2_FP_b37",
        "IDT_Exome_v2_FP"="IDT_Exome_v2_FP_b37",
        "IMPACT505_BAITS"="IMPACT505_b37",
        "IMPACT505"="IMPACT505_b37",
        "IMPACT410"="IMPACT410_b37",
    	"Twist_mWES"="Twist_mWES_mm10",
        "Ganesh_ZFP36_Expanded"="Ganesh_ZFP36_Expanded_b37"
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

} else {
    cat("\n\tNo bait set specified\n")
    cat("\tUsing",request$Species,"wgs target files\n\n")
    if(request$Species=="Human") {
        assay="wgs_b37"
        assayPath="/juno/projects/BIC/targets/designs/wgs_b37"
    } else if(request$Species=="Mouse") {
        assay="wgs_mm10"
        assayPath="/juno/projects/BIC/targets/designs/wgs_mm10"
    } else if(request$Species=="Pig") {
        assay="wgs_Sscrofa11.1"
        assayPath="/juno/projects/BIC/targets/designs/wgs_Sscrofa11.1"
    } else {
        stop("ERROR: Unknown Species")
    }

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

#
# Check assay and update as needed
# For M-IMPACT add pooled normal
#

if(requestVar$Assay=="M-IMPACT_v2_mm10") {
    mostRecentPool=sort(fs::dir_ls("../zz_M_IMPACT_Pools",regex="zz_M-IMPACT__POOLEDNORMAL__"),decreasing=T)[1]
    mapPool=read_tsv(mostRecentPool,col_names=F)
    mapping=bind_rows(mapping,mapPool)
    fs::file_move(mappingFile,paste0(mappingFile,".orig"))
    write_tsv(mapping,mappingFile,col_names=F)
}

mapping %>%
    distinct(X2) %>%
    mutate(Group=sprintf("Group_%02d",row_number())) %>%
    write_tsv(gsub("metadata.yaml","sample_grouping.txt",rFile),col_names=F)

sampleMeta=read_csv(gsub(".yaml","_samples.csv",rFile),show_col_types=F) %>%
    filter(IGOComplete) %>%
    mutate(SID=cc("s",investigatorSampleId)) %>%
    select(SID,PID=cmoPatientId,Class=tumorOrNormal) %>%
    arrange(PID,Class)

# normals=sampleMeta %>% filter(Class=="Normal") %>% select(PID,Normal=SID)
# tumors=sampleMeta %>% filter(Class!="Normal") %>% select(PID,Tumor=SID)
# pairing=tumors %>% left_join(normals) %>% select(Normal,Tumor) %>% arrange(Normal)

#
# Write pairing manifest
#
openxlsx::write.xlsx(list(metadata=sampleMeta),gsub("metadata.yaml","pairing_manifest.xlsx",rFile))
