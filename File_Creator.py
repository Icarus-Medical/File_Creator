#Author: Ben Scire
#Script to auotmatically create fusion files for orders in the travelers
import adsk.core, adsk.fusion, traceback, requests, math, sys
from . import Api
from datetime import date

app = adsk.core.Application.get()
ui  = app.userInterface
des = app.activeProduct
root = des.rootComponent
api = Api.Api()

def getOrder(orderId):
    #This is pulling all the data from the travelers, same as Icarus Add In with some added variables 
    try: 
        response = api.get(f"/api/order/{orderId}")
        data = response.data

        patientName    = data["patientName"]
        model          = data["catalog"] #same setup as leg["name"]
        step           = data["lastJobEvent"] #if None traveler has not been started 
        engraving      = data["engraving"]
        leg            = data["leg"]
        product        = data["product"]
        location       = data["location"]
        travelerStatus = data["travelerStatus"] #'NEW' 'VERIFIED' or 'ARCHIVED'
        status         = data["status"] #open or pending

        return {
            "patientName"           : patientName,
            "engraving"             : engraving if engraving is not None else "",
            "leg"                   : leg["name"] if leg is not None else "",
            "top_serial_number"     : product["serialTop"] if product is not None else "",
            "bottom_serial_number"  : product["serialBot"] if product is not None else "",
            "hanger"                : (location["account"]["id"] == 3) if location is not None else False,
            "va"                    : (location['account']['type']['id'] == 2) if location is not None else False,
            "bilateral"             : False,
            "catalog"               : model["name"] if model is not None else "",
            "lastJobEvent"          : step,
            "travelerStatus"        : travelerStatus,
            "status"                : status["name"] if status is not None else ""
        }
    except:
        return {
            "engraving"             : "",
            "leg"                   : "",
            "top_serial_number"     : "",
            "bottom_serial_number"  : "",
            "hanger"                : False,
            "va"                    : False,    
            "flexion"               : False,
            "bilateral"             : False
        }

def file_copy(fileName, orientation, a3):
    #This function grabs the proper starter file and creates a copy into the production folder 
    #file name is fed as an input and orientation as well to pick the right starter file
    #a3 is a boolean that says if this is an Ascneder 3.0 

    productionFolder = app.data.findFolderById('urn:adsk.wipprod:fs.folder:co.EgnkouHiTqeVUlInebHVzg') #Grabbing production folder by unique folder ID

    #searching through production subFolders by name to grab relevant folders
    for folder in productionFolder.dataFolders:
        if folder.name == '2024 Patient Files':
            patientFilesFolder = folder
        elif folder.name == 'Ascender Fitment Starters':
            starterFileFolder = folder
        elif folder.name == "KAFO":
            kafoFolder = folder


    #Grabbing starter files by unique ID. You could also loop through the files and find by name, dont think it matters
    leftStarter = starterFileFolder.dataFiles.itemById("urn:adsk.wipprod:dm.lineage:Axlch_JzSh2eXQugDw6sEg")    
    rightStarter = starterFileFolder.dataFiles.itemById("urn:adsk.wipprod:dm.lineage:QZ7I-dyIQ4ayWBotc3zdjw")
    a3Starter = starterFileFolder.dataFiles.itemById("urn:adsk.wipprod:dm.lineage:YxVWVPAgS-OMBbrvofjM4g")

    #Deciding which starter file will be used based on order id input
    if a3:
        activeDoc = a3Starter
    else:
        if orientation == 'left':
            activeDoc = leftStarter
        else:
            activeDoc = rightStarter

    #Grabbing the date and current month as a string to match with proper month folder
    today = date.today().strftime("%B %d, %Y")
    currentMonth = today.split()[0]

    #going inside patient files and finding folder that matches the current month 
    for month in patientFilesFolder.dataFolders:
        if month.name == currentMonth:
            targetFolder = month

    #This is the actual command that copies the selected doc into the current month folder
    newFile = activeDoc.copy(targetFolder)
    newFile.name = fileName 


def file_exe(orderId, request):
    #the actual execution file, takes in order ID, grabs the traveler data
    #uses it to create the fileName string. That is then fed into the fileCopy function
    
    #Pulling relevant patient variables from the getOrder function
    orientation    = request["leg"].lower()
    patientName    = request["patientName"]
    model          = request["catalog"] #this tells me if its Ascender, KAFO or A3.0
    step           = request["lastJobEvent"] #if None, traveler is not started
    travelerStatus = request["travelerStatus"]

    if model == 'Ascender - Custom' or model == 'Ascender 3 - Custom':
    #split patientName into first and last
        nameList = patientName.split()
        firstName = nameList[0]
        try:
            lastName = nameList[1]
        except:
            lastName = ' '

        #Checking if the model is an ascender 3. If '3' is present as the 2nd word
        if model.split()[1] == "3":
            a3 = True
        else:
            a3 = False
        #Pairing orientation with our shorthand naming convention
        if orientation == 'left':
            legName = 'L'
        else:
            legName = "R"
        idName = str(orderId)

        #Creating one string with our file naming convention, this is fed into the file_copy function
        fileName = idName + "_" + lastName + "_" + firstName + "_" + legName

        #Check if traveler is Not Started and  not archived, execute file_copy
        if step is None and travelerStatus != "ARCHIVED":
            #app.log(str(orderId))
            file_copy(fileName, orientation, a3)

#i need to grab these automatically. Check if traveler is not started and if it is not archived, then create

#Setting a range of order Ids to iterate through and create files for
#This needs to be manually updated by the user (need to change this)
upperBoundId = 13473
lowerBoundId = 13455
for i in range(lowerBoundId,upperBoundId+1):
    request = getOrder(i)

    #Checking to make sure order is open and not pending
    try:
        orderStatus = request["status"]
        exe = True
    except:
        exe = False

    if orderStatus == "Open" and exe:
        file_exe(i, request)


