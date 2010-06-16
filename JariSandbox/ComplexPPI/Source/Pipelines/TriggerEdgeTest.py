# Optimize parameters for event detection and produce event and trigger model files

# most imports are defined in Pipeline
from Pipeline import *
import sys, os

from optparse import OptionParser
optparser = OptionParser()
optparser.add_option("-e", "--test", default=Settings.DevelFile, dest="testFile", help="Test file in interaction xml")
optparser.add_option("-r", "--train", default=Settings.TrainFile, dest="trainFile", help="Train file in interaction xml")
optparser.add_option("-o", "--output", default=None, dest="output", help="output directory")
optparser.add_option("-a", "--task", default=1, type="int", dest="task", help="task number")
optparser.add_option("-p", "--parse", default="split-McClosky", dest="parse", help="Parse XML element name")
optparser.add_option("-t", "--tokenization", default="split-McClosky", dest="tokenization", help="Tokenization XML element name")
optparser.add_option("-m", "--mode", default="BOTH", dest="mode", help="MODELS (recalculate SVM models), GRID (parameter grid search) or BOTH")
# Classifier
optparser.add_option("-c", "--classifier", default="Cls", dest="classifier", help="")
optparser.add_option("--csc", default="", dest="csc", help="")
# Example builders
optparser.add_option("-f", "--triggerExampleBuilder", default="GeneralEntityTypeRecognizerGztr", dest="triggerExampleBuilder", help="")
optparser.add_option("-g", "--edgeExampleBuilder", default="MultiEdgeExampleBuilder", dest="edgeExampleBuilder", help="")
# Id sets
optparser.add_option("-v", "--triggerIds", default=None, dest="triggerIds", help="Trigger detector SVM example class and feature id file stem (files = STEM.class_names and STEM.feature_names)")
optparser.add_option("-w", "--edgeIds", default=None, dest="edgeIds", help="Edge detector SVM example class and feature id file stem (files = STEM.class_names and STEM.feature_names)")
# Parameters to optimize
optparser.add_option("-x", "--triggerParams", default="1000,5000,10000,20000,50000,80000,100000,150000,180000,200000,250000,300000,350000,500000,1000000", dest="triggerParams", help="Trigger detector c-parameter values")
optparser.add_option("-y", "--recallAdjustParams", default="0.5,0.6,0.65,0.7,0.85,1.0,1.1,1.2", dest="recallAdjustParams", help="Recall adjuster parameter values")
optparser.add_option("-z", "--edgeParams", default="5000,7500,10000,20000,25000,28000,50000,60000,65000", dest="edgeParams", help="Edge detector c-parameter values")
(options, args) = optparser.parse_args()

# Check options
assert options.mode in ["MODELS", "FINAL", "BOTH"]
assert options.output != None
assert options.task in [1, 2]

if options.csc.find(",") != -1:
    options.csc = options.csc.split(",")
else:
    options.csc = [options.csc]

exec "CLASSIFIER = " + options.classifier

# Main settings
PARSE=options.parse
TOK=options.tokenization
PARSE_TAG = PARSE + "_" + TOK
TRAIN_FILE = options.trainFile
TEST_FILE = options.testFile

# Example generation parameters
EDGE_FEATURE_PARAMS="style:trigger_features,typed,directed,no_linear,entities,genia_limits,noMasking,maxFeatures"
TRIGGER_FEATURE_PARAMS="style:typed"

boosterParams = [float(i) for i in options.recallAdjustParams.split(",")] 

# These commands will be in the beginning of most pipelines
WORKDIR=options.output
CSC_WORKDIR = os.path.join("CSCConnection",WORKDIR.lstrip("/"))

workdir(WORKDIR, False) # Select a working directory, don't remove existing files
log() # Start logging into a file in working directory

TRIGGER_EXAMPLE_BUILDER = eval(options.triggerExampleBuilder)
EDGE_EXAMPLE_BUILDER = eval(options.edgeExampleBuilder)

# Pre-calculate all the required SVM models
TRIGGER_IDS = "trigger-ids"
EDGE_IDS = "edge-ids"
if options.mode in ["BOTH", "MODELS"]:
    if options.triggerIds != None:
        TRIGGER_IDS = copyIdSetsToWorkdir(options.triggerIds)
    if options.edgeIds != None:
        EDGE_IDS = copyIdSetsToWorkdir(options.edgeIds)
    
    ###############################################################################
    # Trigger example generation
    ###############################################################################
    TRIGGER_TRAIN_EXAMPLE_FILE = "trigger-train-examples-"+PARSE_TAG
    TRIGGER_TEST_EXAMPLE_FILE = "trigger-test-examples-"+PARSE_TAG
    print >> sys.stderr, "Trigger examples for parse", PARSE_TAG   
    TRIGGER_EXAMPLE_BUILDER.run(TRAIN_FILE, TRIGGER_TRAIN_EXAMPLE_FILE, PARSE, TOK, TRIGGER_FEATURE_PARAMS, TRIGGER_IDS)
    TRIGGER_EXAMPLE_BUILDER.run(TEST_FILE, TRIGGER_TEST_EXAMPLE_FILE, PARSE, TOK, TRIGGER_FEATURE_PARAMS, TRIGGER_IDS)
    
    ###############################################################################
    # Trigger models
    ###############################################################################
    print >> sys.stderr, "Trigger models for parse", PARSE_TAG
    TRIGGER_CLASSIFIER_PARAMS="c:" + options.triggerParams
    if "local" not in options.csc:
        clear = False
        if "clear" in options.csc: clear = True
        if "louhi" in options.csc:
            c = CSCConnection(CSC_WORKDIR+"/trigger-models", "jakrbj@louhi.csc.fi", clear)
        else:
            c = CSCConnection(CSC_WORKDIR+"/trigger-models", "jakrbj@murska.csc.fi", clear)
    else:
        c = None
    bestTriggerModel = optimize(CLASSIFIER, Ev, TRIGGER_TRAIN_EXAMPLE_FILE, TRIGGER_TEST_EXAMPLE_FILE,\
        TRIGGER_IDS+".class_names", TRIGGER_CLASSIFIER_PARAMS, "trigger-models", None, c, True)[1]
    
    ###############################################################################
    # Edge example generation
    ###############################################################################
    EDGE_TRAIN_EXAMPLE_FILE = "edge-train-examples-"+PARSE_TAG
    EDGE_TEST_EXAMPLE_FILE = "edge-test-examples-"+PARSE_TAG
    print >> sys.stderr, "Edge examples for parse", PARSE_TAG  
    EDGE_EXAMPLE_BUILDER.run(TRAIN_FILE, EDGE_TRAIN_EXAMPLE_FILE, PARSE, TOK, EDGE_FEATURE_PARAMS, EDGE_IDS)
    EDGE_EXAMPLE_BUILDER.run(TEST_FILE, EDGE_TEST_EXAMPLE_FILE, PARSE, TOK, EDGE_FEATURE_PARAMS, EDGE_IDS)
    
    ###############################################################################
    # Edge models
    ###############################################################################
    print >> sys.stderr, "Edge models for parse", PARSE_TAG
    EDGE_CLASSIFIER_PARAMS="c:" + options.edgeParams
    if "local" not in options.csc:
        clear = False
        if "clear" in options.csc: clear = True
        if "louhi" in options.csc:
            c = CSCConnection(CSC_WORKDIR+"/edge-models", "jakrbj@louhi.csc.fi", clear)
        else:
            c = CSCConnection(CSC_WORKDIR+"/edge-models", "jakrbj@murska.csc.fi", clear)
    else:
        c = None
    bestEdgeModel = optimize(CLASSIFIER, Ev, EDGE_TRAIN_EXAMPLE_FILE, EDGE_TEST_EXAMPLE_FILE,\
        EDGE_IDS+".class_names", EDGE_CLASSIFIER_PARAMS, "edge-models", None, c, True)[1]
else:
    # New feature ids may have been defined during example generation, 
    # so use for the grid search the id sets copied to WORKDIR during 
    # model generation. The set files will have the same names as the files 
    # they are copied from
    if options.triggerIds != None:
        TRIGGER_IDS = os.path.basename(options.triggerIds)
    if options.edgeIds != None:
        EDGE_IDS = os.path.basename(options.edgeIds)
    bestEdgeModel = "edge-models/model-c_28000"
    bestTriggerModel = "trigger-models/model-c_180000"

###############################################################################
# Classification with recall boosting
###############################################################################
if options.mode in ["BOTH", "FINAL"]:
    # Pre-made models
    #EDGE_MODEL_STEM = "edge-models/model-c_"
    #TRIGGER_MODEL_STEM = "trigger-models/model-c_"
    
    count = 0
    TRIGGER_EXAMPLE_BUILDER.run(TEST_FILE, "test-trigger-examples", PARSE, TOK, TRIGGER_FEATURE_PARAMS, TRIGGER_IDS)
    bestResults = None
    for boost in boosterParams:
        print >> sys.stderr, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        print >> sys.stderr, "Processing params", str(count) + "/" + str(len(boosterParams)), boost
        print >> sys.stderr, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        
        # Build trigger examples
        CLASSIFIER.test("test-trigger-examples", bestTriggerModel, "test-trigger-classifications")
        evaluator = Ev.evaluate("test-trigger-examples", "test-trigger-classifications", TRIGGER_IDS+".class_names")
        #boostedTriggerFile = "TEST-predicted-triggers.xml"
        #xml = ExampleUtils.writeToInteractionXML("test-trigger-examples", ExampleUtils.loadPredictionsBoost("test-trigger-classifications", boost), TEST_FILE, None, TRIGGER_IDS+".class_names", PARSE, TOK)    
        #xml = ExampleUtils.writeToInteractionXML("test-trigger-examples", "test-trigger-classifications", TEST_FILE, None, TRIGGER_IDS+".class_names", PARSE, TOK)    
        xml = BioTextExampleWriter.write("test-trigger-examples", "test-trigger-classifications", TEST_FILE, None, TRIGGER_IDS+".class_names", PARSE, TOK)
        # Boost
        xml = RecallAdjust.run(xml, boost, None)
        xml = ix.splitMergedElements(xml, None)
        xml = ix.recalculateIds(xml, None, True)
        
        # Build edge examples
        EDGE_EXAMPLE_BUILDER.run(xml, "test-edge-examples", PARSE, TOK, EDGE_FEATURE_PARAMS, EDGE_IDS)
        # Classify with pre-defined model
        CLASSIFIER.test("test-edge-examples", bestEdgeModel, "test-edge-classifications")
        # Write to interaction xml
        evaluator = Ev.evaluate("test-edge-examples", "test-edge-classifications", EDGE_IDS+".class_names")
        if evaluator.getData().getTP() + evaluator.getData().getFP() > 0:
            #xml = ExampleUtils.writeToInteractionXML("test-edge-examples", "test-edge-classifications", xml, None, EDGE_IDS+".class_names", PARSE, TOK)
            xml = BioTextExampleWriter.write("test-edge-examples", "test-edge-classifications", xml, None, EDGE_IDS+".class_names", PARSE, TOK)
            xml = ix.splitMergedElements(xml, None)
            xml = ix.recalculateIds(xml, "final.xml", True)
            
            # EvaluateInteractionXML differs from the previous evaluations in that it can
            # be used to compare two separate GifXML-files. One of these is the gold file,
            # against which the other is evaluated by heuristically matching triggers and
            # edges. Note that this evaluation will differ somewhat from the previous ones,
            # which evaluate on the level of examples.
            EvaluateInteractionXML.run(Ev, xml, TEST_FILE, PARSE, TOK)
                
            # Post-processing
            xml = unflatten(xml, PARSE, TOK)
            
            # Output will be stored to the geniaformat-subdirectory, where will also be a
            # tar.gz-file which can be sent to the Shared Task evaluation server.
            gifxmlToGenia(xml, "geniaformat", options.task)
            
            # Evaluation of the Shared Task format
            results = evaluateSharedTask("geniaformat", options.task)
            if bestResults == None or bestResults[1]["approximate"]["ALL-TOTAL"]["fscore"] < results["approximate"]["ALL-TOTAL"]["fscore"]:
                bestResults = (boost, results)
        else:
            print >> sys.stderr, "No predicted edges"
        count += 1
    print >> sys.stderr, "Booster search complete"
    print >> sys.stderr, "Tested", count, "out of", count, "combinations"
    print >> sys.stderr, "Best booster parameter:", bestResults[0]
    print >> sys.stderr, "Best result:", bestResults[1]
    
