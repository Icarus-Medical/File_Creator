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


def parseStl(meshData):
    meshName = ""
    coordinates = []
    normalVectors = []

    # Decode the data and split into individual lines
    bytes = bytearray(meshData)
    lines = bytes.splitlines()

    # Iterate over lines
    for i, lineBytes in enumerate(lines):

        # Split the line by spaces
        line = lineBytes.decode().strip().split(" ")

        # First line of file has format "solid <mesh name>"
        if i == 0:
            if line[0] != "solid":
                raise Exception("First line of the .stl must start with 'solid'")
            meshName = line[1]

        # Last line of file has format "endsolid <mesh name>"
        elif i == len(lines) - 1:
            if line[0] != "endsolid":
                raise Exception("Last line of the .stl must start with 'endsolid'")
            if line[1] != meshName:
                raise Exception("Last line of the .stl must end with the mesh name")

        # First line in group of 7 has format "facet normal <x> <y> <z>"
        elif (i - 1) % 7 == 0:
            if line[0] != "facet" or line[1] != "normal":
                raise Exception(f"Line {i} of the .stl must begin with 'facet normal'")
            normalVectors.append(float(line[2]))
            normalVectors.append(float(line[3]))
            normalVectors.append(float(line[4]))

        # Second line in group of 7 is "outer loop"
        elif (i - 2) % 7 == 0:
            if line[0] != "outer" or line[1] != "loop":
                raise Exception(f"Line {i} of the .stl must be 'outer loop'")

        # Third, fourth, and fifth lines in group of 7 have format "vertex <x> <y> <z>"
        elif (i - 3) % 7 == 0 or (i - 4) % 7 == 0 or (i - 5) % 7 == 0:
            if line[0] != "vertex":
                raise Exception(f"Line {i} of the .stl must begin with 'vertex'")
            coordinates.append(float(line[1]))
            coordinates.append(float(line[2]))
            coordinates.append(float(line[3]))

        # Sixth line in group of 7 is "endloop"
        elif (i - 6) % 7 == 0:
            if line[0] != "endloop":
                raise Exception(f"Line {i} of the .stl must be 'endloop'")

        # Seventh line in group of 7 is "endfacet"
        elif (i - 7) % 7 == 0:
            if line[0] != "endfacet":
                raise Exception(f"Line {i} of the .stl must be 'endfacet'")

        # Should never hit this case
        else:
            raise Exception(f"Parsing failed for .stl on line {i}")

    return meshName, coordinates, normalVectors

def file_copy(fileName, order, coordinates, normalVectors):
    #This function grabs the proper starter file and creates a copy into the production folder 

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

    #Pulling relevant patient variables from the getOrder function
    orientation    = order["leg"].lower()
    model          = order["catalog"] #this tells me if its Ascender, KAFO or A3.0
    step           = order["lastJobEvent"] #if None, traveler is not started
    travelerStatus = order["travelerStatus"]

    if model == 'Ascender - Custom' or model == 'Ascender 3 - Custom':
        #Checking if the model is an ascender 3. If '3' is present as the 2nd word
        if model.split()[1] == "3":
            a3 = True
        else:
            a3 = False

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

    targetFolder = kafoFolder #temporary for testing

    #setting fileName to our format
    fileNameChopped = fileName.split('_')
    fileNameFormatted = fileNameChopped[0] + '_' + fileNameChopped[1] + '_' + fileNameChopped[2] + '_' + fileNameChopped[3]

    #This is the actual command that copies the selected doc into the current month folder
    if travelerStatus != "ARCHIVED":
        newFile = activeDoc.copy(targetFolder)
        newFile.name = fileNameFormatted
    return newFile

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
        meshData = data["mesh"]["data"]
        meshName, coordinates, normalVectors = parseStl(meshData)
        wireframe = data["wireframe"]



        # x = leftHingePos[0]
        # y = leftHingePos[1]
        # z = leftHingePos[2]

        # Create a new Fusion file
        try:
            # Check to make sure order is open
            if order["status"] == "Open":
                docData = file_copy(fileName, order, coordinates, normalVectors)
                

                # File creation was successful. Remove from the list of builder files
                #app.log(f"Import successful. Removing data for file {fileLabel}")
                #api.post(f"/api/fusionFile/{file['id']}/delete", {})
        except:
            app.log(f"Import failed for file {fileLabel}")
        
        pointCreator(docData, wireframe, coordinates, normalVectors)

    # product = app.activeProduct
    # root = adsk.fusion.Design.cast(product).rootComponent


def pointCreator(docData, wireframe, coordinates, normalVectors):
        doc = app.documents.open(docData, False)
        des: adsk.fusion.Design = doc.products.itemByProductType('DesignProductType')
        root = des.rootComponent

        nodes = []
        leftHingePos = wireframe["leftHingePos"]
        rightHingePos = wireframe['rightHingePos']
        botCuffPos = wireframe["botCuffPos"]
        botLeftCuffPos = wireframe['botLeftCuffPos']
        botLeftFramePos = wireframe['botLeftFramePos']
        botLeftPos = wireframe['botLeftPos']
        botRightCuffPos = wireframe['botRightCuffPos']
        botRightFramePos = wireframe['botRightFamePos']
        botRightPos = wireframe['botRightPos']
        topCuffPos = wireframe['topCuffPos']
        topLeftCuffPos = wireframe['topLeftCuffPos']
        topLeftFramePos = wireframe["topLeftFramePos"]
        topLeftPos = wireframe['topLeftPos']
        topRightCuffPos = wireframe["topRightCuffPos"]
        topRightFramePos = wireframe['topRightFramePos']
        topRightPos = wireframe['topRightPos']
        nodes.extend((topRightPos, topRightFramePos, topRightCuffPos, topLeftPos,topLeftFramePos,topLeftCuffPos,topCuffPos,botRightPos,
                     botRightFramePos,botRightCuffPos,botLeftPos,botLeftFramePos,botLeftCuffPos,botCuffPos,rightHingePos,leftHingePos))
    

        # Create a sketch with a single circle.
        sk: adsk.fusion.Sketch = root.sketches.add(root.xYConstructionPlane)

        
        for node in nodes:
            pt = adsk.core.Point3D.create(node[0]/10,(node[2]/10) + 8.38,node[1]/10)
            sk.sketchPoints.add(pt)

        # meshBodies = root.meshBodies
        # leg = meshBodies.addByTriangleMeshData(coordinates, [], normalVectors, [])
            




importFiles()