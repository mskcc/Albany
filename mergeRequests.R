len<-function(...) length(...)

suppressPackageStartupMessages(require(tidyverse))

projNo=gsub("^Proj_","",basename(getwd()))

mappingFiles=fs::dir_ls(regex="_sample_mapping.txt$") %>% sort
metadataFiles=fs::dir_ls(regex="\\.yaml$")
metadataSampleFiles=fs::dir_ls(regex="_metadata_samples.csv$")

mapping=map(mappingFiles,read_tsv,col_names=F,show_col_types=F,progress=F) %>%
    bind_rows %>%
    arrange(X2)
write_tsv(mapping,paste0("Proj_",projNo,"_sample_mapping.txt"),col_names=F)

metaSamples=map(metadataSampleFiles,read_csv,show_col_types=F,progress=F) %>% bind_rows
write_csv(metaSamples,paste0("Proj_",projNo,"_metadata_samples.csv"))


metadata=yaml::read_yaml(metadataFiles[1])
metadata$requestId=projNo
metadata$NumberOfSamples=nrow(mapping)
yaml::write_yaml(metadata,paste0("Proj_",projNo,"_metadata.yaml"))


fs::dir_create("meta")
map(mappingFiles,fs::file_move,"meta")
map(metadataFiles,fs::file_move,"meta")
map(metadataSampleFiles,fs::file_move,"meta")
