FROM amazonlinux  
 
 
RUN yum -y install which unzip aws-cli tar
RUN yum -y install java-1.8.0 
RUN yum install -y postgresql-server postgresql-contrib  
 
#ENV http_proxy "" 
#ENV https_proxy "" 
ADD fetch_and_run.sh /usr/local/bin/fetch_and_run.sh 
RUN ["chmod", "+x", "/usr/local/bin/fetch_and_run.sh"] 
 
WORKDIR /tmp 
#USER nobody 
ENTRYPOINT ["/usr/local/bin/fetch_and_run.sh"] 
