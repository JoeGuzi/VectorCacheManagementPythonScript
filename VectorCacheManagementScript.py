""" ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------###
Description: This script manages the update process of our Vector cached map services
 
Beginning with: VectorCacheManagementScript.py
 
Created on: 7/24/2017
 
Purpose: This script was written to manage the update process of
    our Vector cached services. It performs a full rebuild of the 
    Vector Tiles and it overwrites the vector tile service on ArcGIS
    Online. This script must be run as the user who owns the service
    Input Username, and password for user who owns vectortilepackage 
    and service Input item ID of uploaded vectortilepackage Input Service 
    Name of service to be overwritten. The portions of this code were stolen
    from Kelly Gerrow (kgerrow@esri.com). https://cloudygis.maps.arcgis.com/home/item.html?id=e94507f5477b4a2c9ecbd1b198e0fad2
 
Authored by: Joe Guzi
 
Previous Production Date:      Production Date: 7/24/2017
 
### ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------"""
 
# Import modules
import arcpy, time, sys, string, os, traceback, datetime, shutil, urllib.request, urllib.parse, urllib.error, json, getpass, arcserver, subprocess, requests, http.client
import xml.dom.minidom as DOM
import xml.etree.ElementTree as ET
from subprocess import Popen
import smtplib
from email.mime.text import MIMEText
# End Import
 
# Setting the arc py environment
ENV= arcpy.env
# End Arcpy Environment
 
# Setting the overwrite of existing features
ENV.overwriteOutput = True
# End Overwrite Setting
 
# Write Log code
logFile = ""
message = ""
 
def writelog(logfile,msg):
    global message
    message += msg
    print (msg)
    f = open(logfile,'a')
    f.write(msg)
    f.close()
 
dateTimeStamp = time.strftime('%Y%m%d%H%M%S')
root = os.path.dirname(sys.argv[0]) #"C:\\Users\\jsguzi\\Desktop"
if not os.path.exists(root + "\\log"): # Check existence of a log folder within the root, if it does not exist it creates one.
    os.mkdir(root + "\\log")
scriptName = sys.argv[0].split("\\")[len(sys.argv[0].split("\\")) - 1][0:-3] #Gets the name of the script without the .py extension 
logFile = root + "\\log\\" + scriptName + "_" + dateTimeStamp[:14] + ".log" #Creates the logFile variable
if os.path.exists(logFile):
    os.remove(logFile)
 
'''
---  These are log examples  ---
message += "Write log message here" + "\n"
exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
formatted_lines = traceback.format_exc().splitlines()
writelog(logFile,message + "\n" + formatted_lines[-1])
writelog(logFile, "Write log message here" + "\n")
---  End log examples  ---
'''
# End Write Log code
 
 
# Functions
def sendEmail(subject, emailMessage):
    #This function is for general success or error emails, sent to SCGIS
    global message
    message += emailMessage
    messages = arcpy.GetMessages()
    writelog(logFile, messages + "\n")
    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
    formatted_lines = traceback.format_exc().splitlines()
    writelog(logFile, formatted_lines[-1] + "\n")
    # Send Email
    # This is the email notification piece [%]
    #email error notification
    smtpserver = 'mailrelay.co.stark.oh.us'
    AUTHREQUIRED = 0 # if you need to use SMTP AUTH set to 1
    smtpuser = ''  # for SMTP AUTH, set SMTP username here
    smtppass = ''  # for SMTP AUTH, set SMTP password here
 
    RECIPIENTS = ['jsguzi@starkcountyohio.gov', 'bwlongenberger@starkcountyohio.gov', 'jmreese@starkcountyohio.gov']
    SENDER = 'gissas@starkcountyohio.gov'
    msg = MIMEText(message) #***i pointed this mime thing at the message
    msg['Subject'] = subject + ' with Script: ' + str(scriptName) ### this is the subject line of the email
    # Following headers are useful to show the email correctly
    # in your recipient's email box, and to avoid being marked
    # as spam. They are NOT essential to the sendmail call later
    msg['From'] = "ArcGIS on GISSAS "
    msg['Reply-to'] = "Joe Guzi "
    msg['To'] = "jsguzi@starkcountyohio.gov"
 
    session = smtplib.SMTP(smtpserver)
    if AUTHREQUIRED:
        session.login(smtpuser, smtppass)
    session.sendmail(SENDER, RECIPIENTS, msg.as_string())
    session.close()

# Returns ssl value and user token Function
def getToken(adminUser, pw):
        data = {'username': adminUser,
            'password': pw,
            'referer' : 'https://www.arcgis.com',
            'f': 'json'}
        url  = 'https://www.arcgis.com/sharing/rest/generateToken'
        jres = requests.post(url, data=data, verify=False).json()
        return jres['token'],jres['ssl']
# End Returns ssl value and user token Function

# RETURNS UNIQUE ORGANIZATION URL and OrgID
def GetAccount(pref, token):
    URL= pref+'www.arcgis.com/sharing/rest/portals/self?f=json&token=' + token
    response = requests.get(URL, verify=False)
    jres = json.loads(response.text)
    return jres['urlKey'], jres['id']
# End RETURNS UNIQUE ORGANIZATION URL and OrgID

# Upload the input TPK, Function
def uploadItem(userName, portalUrl, TPK, itemID, layerName, extent, token):
    #Upload the input TPK, this is using a post request through the requests module,
    #returns a response of success or failure of the uploaded TPK. This can then be used to update the tiles
    #in the tile service

    #update Item URL
    updateUrl = '{}.maps.arcgis.com/sharing/rest/content/users/{}/items/{}/update'.format(portalUrl,userName,itemID)
    #opens Tile Package
    filesUp = {"file": open(TPK, 'rb')}

    #data for request. as this is updated an existing item, the value of overwrite is set to true
    data = {'f':'json',
        'token':token,
        'name':layerName,
        'title': layerName,
        'itemId':itemID,
        'filetype': 'Tile Package',
        'overwrite': 'true',
        'async':'true',
        'extent':extent}
    #submit requst
    response = requests.post(updateUrl, data=data, files=filesUp, verify=False).json()

    return response
# End Upload the input TPK, Function

# Update Tiles Function
def updateTiles(orgID, layerName, extent, lods,token):
   #Build each tile of the tiled service.
   url = "https://tiles.arcgis.com/tiles/{}/arcgis/rest/admin/services/{}/VectorTileServer/updateTiles".format(orgID, layerName)
   data = {"extent": extent,"levels": lods,"token":token, 'f':'json'}
   jres = requests.post(url, data, verify=False).json()
    #returns jobID
   return jres
# End Update Tiles Function

# Create Vector Tile Package and Overwrite AGO Function
def CreateVectorTilePackageOverwriteAGO(MapName,VectorTPK, MinCacheScale, MaxCacheScale, VectorTileIndex, Summary, Tags, inItemID, layerName, extent, lods):
    global VectorCacheProject
    global user
    global pw

    # Process: Define ArcGIS Project
    writelog(logFile, "Process: Define ArcGIS Project" + "\n")
    VectorCacheProject = arcpy.mp.ArcGISProject(VectorCacheProject)
    writelog(logFile, "Process: Define ArcGIS Project Complete!" + "\n")

    # Process: Select the Map
    writelog(logFile, "Process: Select the Map" + "\n")
    Map = VectorCacheProject.listMaps(MapName)
    writelog(logFile, "Process: Select the Map Complete!" + "\n")

    # Process: Create Vector Tile Package
    writelog(logFile, "Process: Create Vector Tile Package" + "\n")
    arcpy.management.CreateVectorTilePackage(Map[0], VectorTPK, "ONLINE", "", "INDEXED", MinCacheScale, MaxCacheScale, VectorTileIndex, Summary, Tags)   
    writelog(logFile, "Process: Create Vector Tile Package Complete" + "\n")

    # get account information
    writelog(logFile, "Process: get account information!" + "\n")
    token= getToken(user, pw)
    if token[1] == False:
        pref='http://'
    else:
        pref='https://'
    writelog(logFile, "Process: get account information Complete!" + "\n")

    # Create Portal URL and assign variables
    writelog(logFile, "Process: Create Portal URL and assign variables!" + "\n")
    t=GetAccount(pref,token[0])
    urlKey=t[0]
    orgID=t[1]
    portalUrl=pref+urlKey
    writelog(logFile, "Process: Create Portal URL and assign variables Complete!" + "\n")


    # upload updated VectorTPK
    writelog(logFile, "Process: upload updated VectorTPK!" + "\n")
    update = uploadItem(user,portalUrl,VectorTPK,inItemID,layerName, extent, token[0])
    writelog(logFile, "Update: " + str(update) + "\n")

    if update['success'] ==True:
        unpack = updateTiles(orgID, layerName, extent, lods, token[0])
    writelog(logFile, "Unpack: " + str(unpack) + "\n")

    # check publishing status until status is complete
    writelog(logFile, "Process: check publishing status until status is complete!" + "\n")
    statusURL ='{}.maps.arcgis.com/sharing/rest/content/users/{}/items/{}/status?jobId={}&f=json&token={}'.format(portalUrl,user,unpack['itemId'],unpack['jobId'],token[0])
    requestStatus = requests.get(statusURL)
    status=requestStatus.json()
    while status['status']=='processing':
        time.sleep(10)
        writelog(logFile, str(status['status']) + "\n")
        statusURL ='{}.maps.arcgis.com/sharing/rest/content/users/{}/items/{}/status?jobId={}&f=json&token={}'.format(portalUrl,user,unpack['itemId'],unpack['jobId'],token[0])
        requestStatus = requests.get(statusURL)
        status=requestStatus.json()

    #print completed status
    writelog(logFile, str(status['status']) + "\n")
    writelog(logFile, "Process: upload updated VectorTPK Complete!" + "\n")




# End Create Vector Tile Package and Overwrite AGO Function
# End Function Section
 
# Variables
user= 'Username' # ArcGIS Online Username It must be the owner of the tile package item and vector tile service
pw = 'Password' # ArcGIS Online Password?')
VectorCacheProject = "C:\\VectorCacheProject\\VectorCacheProject.aprx" # This is the project used to create the Vector Tile Package

# Cache 1 Variables
Cache1_ProMapName = "Cache1" # name of the map in the ArcGIS Pro Project
Cache1_tpk =  "C:\\VectorCacheProject\\VectorCaches\\Packages\\Cache1VectorCache.vtpk" # location of VTPK
Cache1_MinCacheScale = 144447.638572 
Cache1_MaxCacheScale = 564.248588
Cache1_Index = "C:\\VectorCacheProject\\VectorCaches\\Projects\\VectorCacheIndexes\\VectorCacheIndexes.gdb\\Cache1VectorCacheIndex" # Vector Cache Index Feature class
Cache1_Summary = "This is the summary of Cache 1."
Cache1_Tags = "Stark, County, Cache1"
Cache1_inItemID= '12345649e97740ce9cc703a6292dce65'# Item ID of the uploaded VTPK
Cache1_layerName ='Cache_1'# Service Name of the vector tile service to overwrite
Cache1_extent = '{"xmin":-81.75,"ymin":40.63,"xmax":-80.99,"ymax":41.01,"spatialReference":{"wkid":102100}}' #'extent'# example'{"xmin":-1.84761407196E7,"ymin":1995253.5241999999,"xmax":-7185123.9953000005,"ymax":1.1525580625400003E7,"spatialReference":{"wkid":102100}}'
Cache1_lods = '11-19' #enter levels in format outlined http://resources.arcgis.com/en/help/arcgis-rest-api/index.html#/Update_Tiles/02r30000022v000000/
# End Cache 1 Variables
# End Variable Section
 
try:
    # Process
    writelog(logFile, "Process:" + "\n")
    writelog(logFile, "STARTING TIME: " + str(datetime.datetime.now()) + "\n")

    # Process: Creating the Cache 1 Vector Tile Package and Over writing ArcGIS Online
    writelog(logFile, "Process: Creating the Cache 1 Vector Tile Package and Over writing ArcGIS Online" + "\n")
    CreateVectorTilePackageOverwriteAGO(Cache1_ProMapName, Cache1_tpk, Cache1_MinCacheScale, Cache1_MaxCacheScale, Cache1_Index, Cache1_Summary, Cache1_Tags, Cache1_inItemID, Cache1_layerName, Cache1_extent, Cache1_lods)
    writelog(logFile, "Process: Creating the Cache 1 Vector Tile Package and Over writing ArcGIS Online Complete!" + "\n")
     
    writelog(logFile, "ENDING TIME: " + str(datetime.datetime.now()) + "\n")   
    writelog(logFile, "Success!" + "\n")
except:
    writelog(logFile, "Error:" + "\n")
    writelog(logFile, "ERROR TIME: " + str(datetime.datetime.now()) + "\n")
    sendEmail("Error", "Error" + "\n")
