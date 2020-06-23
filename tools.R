normalizeName<-function(nn) {

    pn=strsplit(nn," ")[[1]]
    lastName=paste(pn[2:len(pn)],collapse=" ")
    paste0(lastName,", ",pn[1])

}
