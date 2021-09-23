require(tidyverse)
args=commandArgs(trailing=T)

fixMappingIDs<-function(mfile) {
    newMap=read_tsv(mfile,col_names=F) %>% mutate(X2=gsub(".*Sample","s",X4) %>%
        gsub("_IGO_.*","",.))
    write_tsv(newMap,basename(mfile),col_names=F)
}

map(args,fixMappingIDs)

