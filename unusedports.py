import sys
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from netmiko.ssh_exception import NetMikoAuthenticationException
import smtplib
import string

#define globals
nodes=[]
LOWPORTS = False
ERROR = False
#add MGMT IPs of devices that you want to only display ports that are marked as having NEVER on the input line here.  
#Meaning that if a port has ever been used, it won't show as available.
#For instance; protected = ('a.b.c.d','b.c.d.e')
protected = ('')
#SET DNS OR IP OR SMTP SERVER HERE
SMTPHOST = ''
#SET HEADER FROM FIELD HERE
FROM = ''
#SET HEADER RECIPIENT FIELD HERE, i.e. "test@abc.com" or "test@abc.com; test2@abc.com"
TO = ''
#SET HEADER SUBJECT FIELD
SUBJECT = ''

#DEFINE USERNAME AND PASSWORD FOR CONNECTING TO DEVICES
USERNAME = ''
PASSWORD = ''

#DEFINE LOW_THRESHOLD, the number of ports you want to alert to 
LOW_THRESHOLD = 10

#Define Function that attempts to connect to device, returns error if cannot connect
def auth_dev(device):
        try:
                return ConnectHandler(**device)
        except (NetMikoTimeoutException, NetMikoAuthenticationException):
                ERROR = True
                return "Failure"
#Function that uses CLI regex to determine ports that have not been found in the last 6 weeks, unless the switch is in the protected list
def getUnusedPorts(tgt):
                #CHECK IF HOST IS PROTECTED, IF SO, RUN REGEX ONLY TO FILTER "NEVER USED"
                if tgt in (protected):
                        cmd = "show int | i proto.*notconnect|proto.*administratively|disabled|Last input never, output never, output hang never"
                else:
                #IF NOT PROTECTED, RUN REGEX TO FILTER 6+ WEEKS OF UNUSED
                        cmd = "show int | i proto.*notconnect|proto.*administratively|Last in.* [6-9]w|Last in.*[0-9][0-9]w|[0-9]y|disabled|Last input never, output never, output hang never"
                  
                #DEFINE DEVICE
                cisco_device = {
                                'device_type':'cisco_ios',
                                'ip':tgt,
                                'username':USERNAME,
                                'password': PASSWORD,
                                }
                #ATTEMPT TO CONNECT TO DEVICE
                net_connect = auth_dev(cisco_device)
                #IF FAILED, QUIT FUNCTION
                if net_connect == "Failure":
                        return None      
                #OTHERWISE, CONTINUE TO ISSUE COMMANDS
                else:
                        output = net_connect.send_command(cmd)
                        output= output.split('\n')
                        hostname = net_connect.find_prompt().strip('#')
                        #SCREENSCRAPE OFF AVAILABLE FastEthernet or GigabitEthernet PORTS
                        blob = []
                        for i in range(0,len(output)):
                                if (output[i].startswith("Giga") or (output[i].startswith("Fast"))) and ("/0/" in str(output[i]) or "0/" in str(output[i])):
                                        if "Last input" in str(output[i+1]):
                                                blob.append((output[i].split(' is')[0].replace('Ethernet',''))+':'+output[i+1].split(',')[0])
                        #CHECK IF NUMBER OF AVAILABLE PORTS IS LOWER THAN DEFINED THRESHOLD, IF SO, APPEND INFO TO NODE LIST
                        low = []
                        if len(blob) < (LOW_THRESHOLD+1):
                                low.append(hostname)
                                low.append(str(len(blob)))
                                LOWPORTS = True
                                return low
#DEFINE FUNCTION TO SEND EMAIL BASED ON LIST OF DEVICES WITH LOW PORT COUNTS
def sendreport(nodes):    
        i=0
        text='LOW PORT WARNING:\n'
        for item in nodes:
                #IF LIST ENTRY IS DEFINED, CONCAT STRING TO ADD ENTRY IN EMAIL
                if item<>None:
                        text+="Switch: "+str(item[0])+' Ports Available: '+str(item[1])+'\n-----------------\n'

        #DEFINE BODY ELEMENT OF EMAIL
        BODY = string.join((
                "From: %s" % FROM,
                "To: %s" % TO,
                "Subject: %s" % SUBJECT ,
                "",
                text
                ), "\r\n")
        #DEFINE SMTP SERVER OBJECT, CONNECT, SEND EMAIL, CLOSE CONNECTION
        s = smtplib.SMTP(host=SMTPHOST, port=25)
        s.sendmail(FROM, [TO], BODY)
        s.quit()
        
#CHECK FOR SUPPLIED SWITCH LIST, IF NONE SUPPLID VIA ARGS, USE DEFAULT SAMPLELIST.LIST FILE TO GATHER PORT INFORMATON
if len(sys.argv)>1:
        with open(sys.argv[1]) as f:
                for line in f:
                        nodes.append(getUnusedPorts(line))
else:
        with open("switches.list") as f:
                for line in f:
                        nodes.append(getUnusedPorts(line))
#SEND REPORT BASED ON LIST OF NODES WITH LOW PORT COUNTS
sendreport(nodes)
