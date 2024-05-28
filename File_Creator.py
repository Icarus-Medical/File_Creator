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

def getOrder(data):
    #This is pulling all the data from the travelers, same as Icarus Add In with some added variables 
    try:
        id             = data["id"]
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
            "id"                    : id,
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
        return None

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


def file_exe(fileName, data, mesh):
    #the actual execution file, takes in order ID, grabs the traveler data
    #uses it to create the fileName string. That is then fed into the fileCopy function
    
    #Pulling relevant patient variables from the getOrder function
    orientation    = data["leg"].lower()
    model          = data["catalog"] #this tells me if its Ascender, KAFO or A3.0
    step           = data["lastJobEvent"] #if None, traveler is not started
    travelerStatus = data["travelerStatus"]

    if model == 'Ascender - Custom' or model == 'Ascender 3 - Custom':
        #Checking if the model is an ascender 3. If '3' is present as the 2nd word
        if model.split()[1] == "3":
            a3 = True
        else:
            a3 = False

        #Check if traveler is Not Started and  not archived, execute file_copy
        if step is None and travelerStatus != "ARCHIVED":
            #app.log(str(orderId))
            file_copy(fileName, orientation, a3)    

def importFiles():
    # Get a list of all builder files ready for import
    app.log("Requesting builder files")
    filesResponse = api.get("/api/fusionFile/all")

    # Make sure the API request was successful
    if filesResponse.status != 200:
        api.log(f"Could not get files. Response: {filesResponse.status} - {filesResponse.reason}")
        return

    data = filesResponse.data

    # Loop through the list of builder files ready for import
    for file in data:
        fileLabel = f"{file['name']} ({file['id']}"

        # Get the data for a specific builder file
        app.log(f"Requesting data for file {fileLabel}")
        fileResponse = api.get(f"/api/fusionFile/{file['id']}")

        # Make sure the API request was successful
        if fileResponse.status != 200:
            app.log(f"Could not get file {fileLabel}). Response: {fileResponse.status} - {fileResponse.reason}")
            continue

        data = fileResponse.data

        # Get the order data for the file
        order = getOrder(data["order"])

        # Make sure we were able to get order data
        if order is None:
            app.log(f"Could not get order data for file {fileLabel}")
            continue

        fileName = data["name"]
        mesh = data["mesh"]

        # Create a new Fusion file
        try:
            # Check to make sure order is open
            if order["status"] == "Open":
                file_exe(fileName, order, mesh)

                # File creation was successful. Remove from the list of builder files
                app.log(f"Import successful. Removing data for file {fileLabel}")
                api.post(f"/api/fusionFile/{file['id']}/delete", {})
        except:
            app.log(f"Import failed for file {fileLabel}")
            
importFiles()