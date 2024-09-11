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

def file_copy(fileName, rigid, model):
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
        elif folder.name == "Wireframe Test Fits":
            testFits = folder

    for file in starterFileFolder.dataFiles:
        if file.name == "A3_Rigid_Base_File":
            a3StarterRigid = file
        elif file.name == "A3_Base_File":
            a3Starter = file

    for folder in kafoFolder.dataFolders:
        if folder.name == "KAFO Starter Files":
            kafoStarters = folder
        if folder.name == "2024 KAFO Patient Files":
            kafoPatients = folder

    for file in kafoStarters.dataFiles:
        if file.name == "A2_TAP_Starter_File":
            tapStarter = file
        elif file.name == "A2_TAD_Starter_File":
            tadStarter = file
        elif file.name == "A2_TPD_Starter_File":
            tpdStarter = file
        elif file.name == "A2_TPP_Starter_File":
            tppStarter = file
            
    if model == "KAFO - Custom":
        kafo = True
    else:
        kafo = False

    if kafo:
        if fileName.split('_')[3] == "TAD":
            activeDoc = tadStarter
        if fileName.split('_')[3] == "TAP":
            activeDoc = tapStarter
        if fileName.split('_')[3] == "TPD":
            activeDoc = tpdStarter
        if fileName.split('_')[3] == "TPP":
            activeDoc = tppStarter

        targetFolder = kafoPatients

    else:
    #Deciding which starter file will be used based on order id input
        if rigid:
            activeDoc = a3StarterRigid
        else:
            activeDoc = a3Starter

        #Grabbing the date and current month as a string to match with proper month folder
        today = date.today().strftime("%B %d, %Y")
        currentMonth = today.split()[0]

        #going inside patient files and finding folder that matches the current month 
        for month in patientFilesFolder.dataFolders:
            if month.name == currentMonth:
                targetFolder = month

    #targetFolder = testFits

    #setting fileName to our format
    fileNameChopped = fileName.split('_')
    if kafo:
        fileNameFormatted = fileNameChopped[0] + '_' + fileNameChopped[1] + '_' + fileNameChopped[2] + '_' + fileNameChopped[3] + '_' + fileNameChopped[4]
    else:
         fileNameFormatted = fileNameChopped[0] + '_' + fileNameChopped[1] + '_' + fileNameChopped[2] + '_' + fileNameChopped[3]

    #This is the actual command that copies the selected doc into the current month folder
    #if travelerStatus != "ARCHIVED":
    newFile = activeDoc.copy(targetFolder)
    newFile.name = fileNameFormatted
    return newFile

def importFiles():

    orderID, cancel = ui.inputBox('Enter Order ID')
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

        traveler_orderID   = data['order']['id']

        if str(traveler_orderID) == orderID:
            fileName = data["name"]
            meshData = data["mesh"]["data"]
            meshName, coordinates, normalVectors = parseStl(meshData)
            rigid = data['order']['hasRigidFrame']
            model = data['order']['catalog']['name']
            wireframe = data["wireframe"]
            model = data['order']['catalog']['name']
            # Create a new Fusion file
            try:
                # Check to make sure order is open
                if order["status"] == "Open":
                    docData = file_copy(fileName, rigid, model)
                    # File creation was successful. Remove from the list of builder files
                    app.log(f"Import successful. Removing data for file {fileLabel}")
                    api.post(f"/api/fusionFile/{file['id']}/delete", {})
            except:
                app.log(f"Import failed for file {fileLabel}")
            #ui.messageBox(model)
            #docData = file_copy(fileName, rigid, model)
            
            if model == "KAFO - Custom":
                kafo = True
            else:
                kafo = False

            fitFrame(docData, wireframe, kafo)


def pointCreator(wireframe):
        nodes = []
        #I'm naming these based on the cross sections they match up with. fitPt1 = CS-1 etc
        fitPt1 = wireframe["leftHingePos"]
        fitPt13 = wireframe['rightHingePos']
        fitPt19 = wireframe["botCuffPos"]
        fitPt20 = wireframe['botLeftCuffPos']
        fitPt22 = wireframe['botLeftFramePos']
        fitPt21 = wireframe['botLeftPos']
        fitPt18 = wireframe['botRightCuffPos']
        fitPt16 = wireframe['botRightFramePos']
        fitPt17 = wireframe['botRightPos']
        fitPt7 = wireframe['topCuffPos']
        fitPt6 = wireframe['topLeftCuffPos']
        fitPt4 = wireframe["topLeftFramePos"]
        fitPt5 = wireframe['topLeftPos']
        fitPt8 = wireframe["topRightCuffPos"]
        fitPt10 = wireframe['topRightFramePos']
        fitPt9 = wireframe['topRightPos']
        nodes.extend((fitPt1,fitPt1,fitPt1,fitPt4,fitPt5,fitPt6,fitPt7,fitPt8,fitPt9,fitPt10,fitPt13,fitPt13,fitPt13,fitPt13,fitPt13,fitPt16,fitPt17,fitPt18,fitPt19,fitPt20,fitPt21,fitPt22, fitPt1, fitPt1))

        return nodes

def ip_mover(i,transform, bip=False):
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = app.activeProduct
    root = design.rootComponent
#function to move all IPs and BIPs with their CSs

    skList = []
    if bip:
        skList.append(root.sketches.itemByName('BIP-' + str(i)))
    else:
        skList.append(root.sketches.itemByName('IP-' + str(i)))
    
    if i == 5:
        skList.append(root.sketches.itemByName('IP-4.5'))
        skList.append(root.sketches.itemByName('IP-5.5'))

    for sk in skList:
        group = adsk.core.ObjectCollection.create()
        #add all sketch components to group
        for crv in sk.sketchCurves:
            group.add(crv)
        for pnt in sk.sketchPoints:
            group.add(pnt)

        sk.move(group, transform) 

    if not bip:
        railSk = root.sketches.itemByName('Pipe-rail-1')
        railGrp = adsk.core.ObjectCollection.create()
        if 1 <= i <= 4:
            railPt = railSk.sketchCurves.sketchFittedSplines.item(0).fitPoints.item(i-1)
        elif i == 5:
            railPt = railSk.sketchCurves.sketchFittedSplines.item(0).fitPoints.item(i-1)
            railPt2 = railSk.sketchCurves.sketchFittedSplines.item(0).fitPoints.item(i)
            railPt3 = railSk.sketchCurves.sketchFittedSplines.item(0).fitPoints.item(i+1)
            railGrp.add(railPt2)
            railGrp.add(railPt3)
        else:
            railPt = railSk.sketchCurves.sketchFittedSplines.item(0).fitPoints.item(i+1)
        railGrp.add(railPt)

        railSk.move(railGrp, transform)
    
def spline_mover(i, transform):
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = app.activeProduct
    root = design.rootComponent
    splineList = ['rail-1', 'rail-2', 'rail-3', 'rail-4', 'rail-5']

    for spline in splineList:
        #function to move a specific spline point i, from the spline inputted
        sk = root.sketches.itemByName(spline)

        group = adsk.core.ObjectCollection.create()
        #add all sketch components to group
        spoint = sk.sketchCurves.sketchFittedSplines.item(0).fitPoints.item(i)
        group.add(spoint)

        sk.move(group, transform)

def hinge_mover(transform, medial=False):
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = app.activeProduct
    root = design.rootComponent
    if medial:
        occ = root.occurrences.itemByName('MedialHinge:1')
    else:
        occ = root.occurrences.itemByName('LateralHinge:1')
    features = occ.component.features
    moveFeats = features.moveFeatures

    bodies = adsk.core.ObjectCollection.create()
    for body in occ.component.bRepBodies:
        bodies.add(body)

    moveFeatureInput = moveFeats.createInput(bodies, transform)
    moveFeats.add(moveFeatureInput)   

def csMover(i, fitPts):
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = app.activeProduct
    root = design.rootComponent

    #add cross section curve and points to group and move together
    group = adsk.core.ObjectCollection.create()
    #Grab sketch based on i
    cs = root.sketches.itemByName('CS-'+ str(i))
    #add all sketch components to group
    for crv in cs.sketchCurves:
        group.add(crv)
    for pnt in cs.sketchPoints:
        group.add(pnt)

    #find inside point on CS as our fromPt
    csPt = cs.sketchCurves.sketchFittedSplines.item(0).fitPoints.item(1).worldGeometry

    cs1Pt = root.sketches.itemByName('CS-1').sketchCurves.sketchFittedSplines.item(0).fitPoints.item(1).worldGeometry
    cs13Pt = root.sketches.itemByName('CS-13').sketchCurves.sketchFittedSplines.item(0).fitPoints.item(1).worldGeometry
    cs10Pt = root.sketches.itemByName('CS-10').sketchCurves.sketchFittedSplines.item(0).fitPoints.item(1).worldGeometry

    fitPt = fitPts[i-1]
    fitPt10 = fitPts[9]


    if 2<= i <= 3 or 23 <= i <= 24:
        fromPt = cs1Pt
    elif 11 <= i <= 12 or 14 <= i <= 15:
        fromPt = cs13Pt
    else:
        fromPt = csPt

    rawTransform = adsk.core.Matrix3D.create()
    rawTransform.translation = fromPt.vectorTo(fitPt)

    dX = rawTransform.translation.x
    dY = rawTransform.translation.y
    dZ = rawTransform.translation.z

    vector10 = cs10Pt.vectorTo(fitPt10)
    zShift = vector10.z

    #specific translation modifiers for cs's
    transform = adsk.core.Matrix3D.create()

    if 1<=i<=3 or 23<=i<=24:
        a = 0.92
    elif 11<=i<=15:
        a = -0.92
    else:
        a = 0

    #isolating cuff cross sections to move in X and Y directions
    if 4 <= i <= 10:
        if 6 <= i <= 8:
            transform.translation = adsk.core.Vector3D.create(dX, dY, zShift)
        else:
            transform.translation = adsk.core.Vector3D.create(dX, 0, zShift) 
    elif 18 <= i <= 20:                                                                                  #BCuff corners flare out
        transform.translation = adsk.core.Vector3D.create(dX, dY, 0)
    else:
        transform.translation = adsk.core.Vector3D.create(dX+a, 0, 0)

    if i == 1:
        hinge_mover(transform, False)
    elif i == 13:
        hinge_mover(transform, True)
        
    cs.move(group, transform)
    spline_mover(i-1, transform)
    if 1 <= i <= 13:
        ip_mover(i, transform)
    elif i == 14 or i == 24:
        ip_mover(i, transform, True)

def shorten_frame(zShift):
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = app.activeProduct
    root = design.rootComponent

    #add cross section curve and points to group and move together
    group = adsk.core.ObjectCollection.create()

    sk = root.sketches.itemByName('Strap pos')

    for line in sk.sketchCurves.sketchLines:
        if line.startSketchPoint.worldGeometry.z > 11:
            group.add(line)

    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(0,zShift,0)

    sk.move(group, transform)
    
# def kafoCreate(docData):
#         doc = app.documents.open(docData, False)
#         des: adsk.fusion.Design = doc.products.itemByProductType('DesignProductType')
#         root = des.rootComponent

#         doc.save('Wireframe fit')

def fitFrame(docData, wireframe, kafo):
        doc = app.documents.open(docData, False)
        des: adsk.fusion.Design = doc.products.itemByProductType('DesignProductType')
        root = des.rootComponent

        if not kafo:
            nodes = pointCreator(wireframe)

            sk = root.sketches.add(root.xYConstructionPlane)

            fitPts = []
            for node in nodes:
                pt = adsk.core.Point3D.create(node[0]/10,(node[2]/10) + 8.38,node[1]/10)
                sk.sketchPoints.add(pt)
                fitPts.append(pt)

            if fitPts[9].z < 10.668:
                shorten = True
                zShift = fitPts[9].z - 10.668
                shorten_frame(zShift)


            leftHinge = [2,3,23,24,1]
            rightHinge = [11,12,14,15,13]


            for n in leftHinge:
                csMover(n, fitPts)

            for x in rightHinge:
                csMover(x, fitPts)

            for i in range(4, 11):
                csMover(i, fitPts)
            for i in range(16, 23):
                csMover(i, fitPts)

            sk.isLightBulbOn = False

        doc.save('Wireframe fit')

        # meshBodies = root.meshBodies
        # leg = meshBodies.addByTriangleMeshData(coordinates, [], normalVectors, [])

def importMesh():
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = app.activeProduct
    root = design.rootComponent
    meshBodies = root.meshBodies
    moveFeats = root.features.moveFeatures

    

    unitMm = adsk.fusion.MeshUnits.MillimeterMeshUnit

    baseFeatures = root.features.baseFeatures
    baseFeature = baseFeatures.add()

    baseFeature.startEdit()

    paths = selectFiles('Select leg STL')

    for path in paths:
        mesh = meshBodies.add(path, unitMm, baseFeature)

    baseFeature.finishEdit()


    meshColl = adsk.core.ObjectCollection.create()
    meshColl.add(meshBodies.item(0))

    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(0, 8.38, 0)

    moveInput = moveFeats.createInput(meshColl, transform)

    moveFeats.add(moveInput)

    

def selectFiles(
    msg :str):

    fileDlg = ui.createFileDialog()
    fileDlg.isMultiSelectEnabled = True
    fileDlg.title = msg
    fileDlg.filter = '*.stl'
    
    dlgResult = fileDlg.showOpen()
    if dlgResult == adsk.core.DialogResults.DialogOK:
        return fileDlg.filenames

def execute():
    importFiles()
    importMesh()


execute()
#importMesh()