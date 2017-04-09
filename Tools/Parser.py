import sys
import codecs
import time
import Tools.GeniaSentenceSplitter as GeniaSentenceSplitter
import Utils.ElementTreeUtils as ETUtils
import Utils.InteractionXML.InteractionXMLUtils as IXMLUtils
import Utils.Align as Align
from Utils.ProgressCounter import ProgressCounter
from collections import defaultdict
import re
import json
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import cElementTree as ET

class Parser:
    def __init__(self):
        self.escDict={"-LRB-":"(",
                 "-RRB-":")",
                 "-LCB-":"{",
                 "-RCB-":"}",
                 "-LSB-":"[",
                 "-RSB-":"]",
                 "``":"\"",
                 "''":"\"",
                 "\\/":"/",
                 "\\*":"*"}
        self.escSymbols = sorted(self.escDict.keys())
    
    ###########################################################################
    # Utilities
    ###########################################################################

    def unescape(self, text):
        for escSymbol in self.escSymbols:
            text = text.replace(escSymbol, self.escDict[escSymbol])
        return text
    
    def getCorpus(self, input):
        print >> sys.stderr, "Loading corpus", input
        corpusTree = ETUtils.ETFromObj(input)
        print >> sys.stderr, "Corpus file loaded"
        corpusRoot = corpusTree.getroot()
        return corpusTree, corpusRoot
    
    def getDocumentOrigId(self, document):
        origId = document.get("pmid")
        if origId == None:
            origId = document.get("origId")
        if origId == None:
            origId = document.get("id")
        return origId
    
    def getSentences(self, corpusRoot, requireEntities=False, skipIds=[], skipParsed=True, parseName="McCC"):
        for sentence in corpusRoot.getiterator("sentence"):
            if sentence.get("id") in skipIds:
                print >> sys.stderr, "Skipping sentence", sentence.get("id")
                continue
            if requireEntities:
                if sentence.find("entity") == None:
                    continue
            if skipParsed:
                if ETUtils.getElementByAttrib(sentence, "parse", {"parser":parseName}) != None:
                    continue
            yield sentence
    
#     def getExtraAttributes(self, parserType, extraAttributes=None, addTimeStamp=False):
#         parseTimeStamp = time.strftime("%d.%m.%y %H:%M:%S")
#         print >> sys.stderr, "Time stamp for " + parserType + " parsing:", parseTimeStamp
#         if extraAttributes == None:
#             extraAttributes = {}
#         extraAttributes[parserType + "-source"] = "TEES" # parser was run through this wrapper
#         if addTimeStamp:
#             extraAttributes[parserType + "-date"] = parseTimeStamp # links the parse to the log file
#         return extraAttributes
    
    def depToString(self, dep):
        print "DEPTOSTRING", dep
        if "t1Word" in dep:
            return dep["type"] + "(" + dep["t1Word"] + "-" + str(dep["t1"]) + ", " + dep["t2Word"] + "-" + str(dep["t2"]) + ")"
        else:
            return dep["type"] + "(" + dep["t1Token"].get("text") + "-" + str(dep["t1"]) + ", " + dep["t2Token"].get("text") + "-" + str(dep["t2"]) + ")"
    
    def getCatenated(self, tokens, tokenSep=" "):
        catenated = ""
        tokenOffsets = []
        for i in range(len(tokens)):
            if i > 0:
                catenated += tokenSep
            tokenOffsets.append(range(len(catenated), len(catenated) + len(tokens[i])))
            catenated += tokens[i]
        return catenated, tokenOffsets
    
    def getFilteredText(self, text, skipRE):
        filtered = ""
        offsets = []
        for i in range(len(text)):
            if skipRE == None or not skipRE.match(text[i]):
                filtered += text[i]
                offsets.append(i)
        return filtered, offsets
    
    def alignTokens(self, tokens, target, tokenSep=" ", skipRE=None, debugId=None, debugMessage="Partial alignment"):
        targetIsString = isinstance(target, basestring)
        if targetIsString:
            target, textOffsets = self.getFilteredText(target, skipRE)
            source, tokenOffsets = self.getCatenated(tokens, tokenSep)
        else:
            source = tokens
        #for char in text:
        alignedText, alignedCat, diff, alignedOffsets = Align.align(target, source)
        mismatchCount = diff.count("*")
        if mismatchCount > 0:
            usedEscapings = []
            for escSymbol in [x for x in sorted(self.escDict.keys()) if x in tokens]:
                newTokens = [x.replace(escSymbol, self.escDict[escSymbol]) for x in tokens]
                if targetIsString:
                    newSource, newTokenOffsets = self.getCatenated(newTokens, tokenSep)
                else:
                    newSource = newTokens
                newAlignedText, newAlignedCat, newDiff, newAlignedOffsets = Align.align(target, newSource)
                newDiffMismatchCount = newDiff.count("*")
                #print "NEWCAT", newCatenated, newDiffMismatchCount
                if newDiffMismatchCount < mismatchCount:
                    mismatchCount = newDiffMismatchCount
                    tokens = newTokens
                    if targetIsString:
                        source, tokenOffsets = newSource, newTokenOffsets
                    alignedText, alignedCat, diff, alignedOffsets = newAlignedText, newAlignedCat, newDiff, newAlignedOffsets
                    usedEscapings.append(escSymbol)
                if newDiffMismatchCount == 0:
                    break
            if mismatchCount > 0 and debugMessage != None:
                print >> sys.stderr, debugMessage, debugId, [source, target], usedEscapings
                Align.printAlignment(alignedText, alignedCat, diff)
        tokenAlignments = []
        #print tokens, tokenOffsets
        #print text, textOffsets
        #print "aligned", alignedOffsets
        if targetIsString:
            tokenAlignments = []
            for tokenIndex in range(len(tokens)):
                tokenAlignedOffsets = [alignedOffsets[x] for x in tokenOffsets[tokenIndex] if alignedOffsets[x] != None]
                if len(tokenAlignedOffsets) == 0:
                    tokenAlignments.append(None)
                else:
                    tokenTextOffsets = [textOffsets[x] for x in tokenAlignedOffsets]
                    tokenAlignments.append((min(tokenTextOffsets), max(tokenTextOffsets) + 1))
            return tokenAlignments
        else:
            return alignedOffsets
    
#     def alignTokens(self, sourceTokens, targetTokens, debugId=None, debugMessage="Partial alignment"):
#         alignedText, alignedCat, diff, alignedOffsets = Align.align(targetTokens, sourceTokens)
#         mismatchCount = diff.count("*")
#         if mismatchCount > 0:
#             usedEscapings = []
#             for escSymbol in [x for x in sorted(self.escDict.keys()) if x in sourceTokens]:
#                 newTokens = [x.replace(escSymbol, self.escDict[escSymbol]) for x in sourceTokens]
#                 newAlignedText, newAlignedCat, newDiff, newAlignedOffsets = Align.align(targetTokens, sourceTokens)
#                 newDiffMismatchCount = newDiff.count("*")
#                 #print "NEWCAT", newCatenated, newDiffMismatchCount
#                 if newDiffMismatchCount < mismatchCount:
#                     mismatchCount = newDiffMismatchCount
#                     sourceTokens = newTokens
#                     alignedText, alignedCat, diff, alignedOffsets = newAlignedText, newAlignedCat, newDiff, newAlignedOffsets
#                     usedEscapings.append(escSymbol)
#                 if newDiffMismatchCount == 0:
#                     break
#             if mismatchCount > 0:
#                 print >> sys.stderr, debugMessage, debugId, [sourceTokens, targetTokens], usedEscapings
#                 Align.printAlignment(alignedText, alignedCat, diff)
#         return alignedOffsets     
    
    ###########################################################################
    # Tokens, Phrases and Dependencies
    ###########################################################################
    
    def mapTokens(self, tokens, tokenization, counts=None, tag="dep-"):
        if counts == None:
            counts = defaultdict(int)
        elements = tokenization.findall("token")
        weights = None #{"match":1, "mismatch":-2, "space":-3, "open":-3, "extend":-3}
        alignedSentence, alignedCat, diff, alignedOffsets = Align.align([x.get("text") for x in elements], [x["text"] for x in tokens], weights=weights)
        if diff.count("|") + diff.count("-") != len(diff):
            print >> sys.stderr, "Partial alignment with existing tokenization"
            Align.printAlignment(alignedSentence, alignedCat, diff)
        for i in range(len(tokens)):
            counts[tag + "tokens-total"] += 1
            elementOffset = alignedOffsets[i]
            if elementOffset != None:
                tokens[i]["element"] = elements[elementOffset]
                counts[tag + "tokens-aligned"] += 1
            else:
                counts[tag + "tokens-not-aligned"] += 1
    
    def addExtraAttributes(self, element, sourceDict, skipKeys):
        for key in sourceDict:
            if key not in skipKeys:
                element.set(key, sourceDict[key])
    
#     def alignIterative(self, tokens, sentence, tokenSep = " "):
#         tokenTexts = [x["text"] for x in tokens]
#         tokensText = tokenSep.join([x["text"] for x in tokens])
#         sentenceText = sentence.get("text")
#         alignedSentence, alignedCat, diff, alignedOffsets = Align.align(sentenceText, tokensText)
#         diffErrorCount = diff.count("|") + diff.count("-")
#         if diffErrorCount != len(diff):
#             for escSymbol in sorted(self.escDict.keys()):
#                 newTokenTexts = [x["text"].replace(escSymbol, self.escDict[escSymbol]) for x in tokens]
#                 newTokensText = tokenSep.join(newTokenTexts)
#                 if newTokensText != tokensText:
#                     newAlignedSentence, newAlignedCat, newDiff, newAlignedOffsets = Align.align(sentenceText, tokensText)
#                     newDiffErrorCount = newDiff.count("|") + newDiff.count("-")
#                     if newDiffErrorCount < diffErrorCount:
#                         alignedSentence, alignedCat, diff, alignedOffsets = newAlignedSentence, newAlignedCat, newDiff, newAlignedOffsets 
#             if diffErrorCount != len(diff):
#                 print >> sys.stderr, "Partial alignment when inserting tokens into sentence", sentence.get("id"), [sentenceText, tokensText]
#                 Align.printAlignment(alignedSentence, alignedCat, diff)
#         return alignedSentence, alignedCat, diff, alignedOffsets
    
    def insertTokens(self, tokens, sentence, tokenization, idStem="t", counts=None, iterativeAlign=True):
        #catenatedTokens, catToToken = self.mapTokens([x["text"] for x in tokens])
        if counts == None:
            counts = defaultdict(int)
#         tokenSep = " "
#         tokensText = tokenSep.join([x["text"] for x in tokens])
#         sentenceText = sentence.get("text")
#         alignedSentence, alignedCat, diff, alignedOffsets = Align.align(sentenceText, tokensText)
#         diffErrorCount = diff.count("|") + diff.count("-")
#         if diffErrorCount != len(diff):   
#             print >> sys.stderr, "Partial alignment when inserting tokens into sentence", sentence.get("id"), [sentenceText, tokensText]
#             Align.printAlignment(alignedSentence, alignedCat, diff)
#         pos = 0
        sentenceText = sentence.get("text")
        charOffsets = self.alignTokens([x["text"] for x in tokens], sentenceText, " ", None, sentence.get("id"), "Partial alignment when inserting tokens into sentence")
        #tokenIndex = 0
        tokKeys = set(["id", "text", "origText", "index", "POS"])
        for i in range(len(tokens)):
            token = tokens[i]
            counts["tokens-parse"] += 1
            #tokenOffsets = [x for x in alignedOffsets[pos:pos + len(token["text"])] if x != None]
            if charOffsets[i] != None: #len(tokenOffsets) > 0:
                #tokenIndex = max(matching, key=lambda key: matching[key])
                # Make element
                element = ET.Element("token")
                element.set("id", idStem + str(i))
                #element.set("i", str(token["index"]))
                element.set("text", token["text"])
                #offset = (min(tokenOffsets), max(tokenOffsets) + 1)
                offset = charOffsets[i]
                matchingText = sentenceText[offset[0]:offset[1]]
                if token["text"] != matchingText:
                    element.set("text", matchingText)
                    element.set("origText", token["text"])
                    #element.set("match", "part")
                    #element.set("matchText", matchingText)
                    counts["tokens-partial-match"] += 1
                else:
                    #element.set("match", "exact")
                    counts["tokens-exact-match"] += 1
                element.set("POS", token.get("POS"))
                self.addExtraAttributes(element, token, tokKeys) # Additional token data
                element.set("charOffset", str(offset[0]) + "-" + str(offset[1]))
                tokenization.append(element)
                token["element"] = element
                counts["tokens-elements"] += 1
            else:
                counts["tokens-no-match"] += 1
            #tokenIndex += 1
            #pos += len(token["text"]) + len(tokenSep)
        if len(tokens) > 0:
            counts["sentences-with-tokens"] += 1

    def insertPhrases(self, phrases, parse, tokens, idStem="p"):
        count = 0
        phrases.sort()
        tokenByIndex = {x["index"]:x for x in tokens}
        for phrase in phrases:
            phraseElement = ET.Element("phrase")
            phraseElement.set("type", phrase["type"])
            phraseElement.set("id", idStem + str(count))
            begin = phrase["begin"]
            end = phrase["end"]
            phraseElement.set("begin", str(phrase["begin"]))
            phraseElement.set("end", str(phrase["end"]))
            t1 = tokenByIndex[begin].get("element")
            t2 = tokenByIndex[end].get("element")
            if t1 != None and t2 != None:
                phraseElement.set("charOffset", t1.get("charOffset").split("-")[0] + "-" + t2.get("charOffset").split("-")[-1])
            parse.append(phraseElement)
            count += 1
            
    def insertDependencies(self, dependencies, sentence, parse, tokenization, idStem="d", counts=None):
        tokensById = {}
        #dependencies = [x for x in dependencies if x["type"] != "root"]
        if tokenization == "LINKED":
            for dep in dependencies:
                assert dep["t1Token"] != None and dep["t2Token"] != None
                tokensById[dep["t1"]] = dep["t1Token"]
                tokensById[dep["t2"]] = dep["t2Token"]
        else:
            for dep in dependencies:
                t1, t2 = dep["t1"], dep["t2"]
                if t1 >= 0: # a root dependency
                    tokensById[t1] = {"text":dep["t1Word"], "id":t1}
                if t2 >= 0: # a root dependency
                    tokensById[t2] = {"text":dep["t2Word"], "id":t2}
            depTokens = [tokensById[i] for i in sorted(tokensById.keys())]
            if tokenization != None:
                self.mapTokens(depTokens, tokenization, counts=counts, tag="dep-")
            else:
                self.insertTokens(depTokens, sentence, tokenization, counts=counts)
        count = 0
        elements = []
        skipped = []
        depKeys = set(["id", "type", "t1", "t2", "t1Word", "t2Word", "t1Token", "t2Token"])
        for dep in dependencies:
            counts["deps-total"] += 1
            t1, t2 = dep["t1"], dep["t2"]
            if t1 == -1 or t2 == -1: # A root dependency
                assert t1 >= 0 or t2 >= 0, dep
                tId = t1 if t1 >= 0 else t2
                tokensById[tId]["element"].set("root", dep["type"])
                count += 1
                counts["deps-root"] += 1
            elif "element" in tokensById[t1] and "element" in tokensById[t2]:
                element = ET.Element("dependency")
                element.set("type", dep["type"])
                element.set("id", idStem + str(count))
                element.set("t1", tokensById[t1]["element"].get("id"))
                element.set("t2", tokensById[t2]["element"].get("id"))
                self.addExtraAttributes(element, dep, depKeys) # Additional token data
                elements.append(element)
                parse.insert(count, element)
                count += 1
                counts["deps-elements"] += 1
            else:
                skipped.append(dep)
                counts["deps-skipped"] += 1
        if count != len(dependencies):
            parse.set("deps-parse", str(len(dependencies)))
            parse.set("deps-inserted", str(count))
        if count == 0:
            if len(dependencies) == 0:
                counts["sentences-with-no-parser-deps"] += 1
            else:
                counts["sentences-with-no-element-deps"] += 1
        else:
            counts["sentences-with-deps"] += 1
        if len(skipped) > 0:
            parse.set("skipped-deps", ", ".join([self.depToString(dep) for dep in skipped]))
            print >> sys.stderr, "Could not align dependencies:", parse.get("skipped-deps")
        return elements
    
    def insertMetadata(self, metadatas, parse, idStem="m"):
        for i in range(len(metadatas)):
            ET.SubElement(parse, "meta", metadatas[i], id=idStem + str(i))
    
    def insertElements(self, sentObjs, sentences, parseName, tokenizerName=None, counter=None, counts=None):
        assert len(sentObjs) == len(sentences), (len(sentObjs), len(sentences))
        if counts == None:
            counts = defaultdict(int)
        if isinstance(counter, basestring):
            counter = ProgressCounter(len(sentences), counter)
        for sentObj, sentence in zip(sentObjs, sentences):
            counts["sentences"] += 1
            if counter != None:
                counter.update(1, "Inserting elements for (" + sentence.get("id") + "): ")
            parse = IXMLUtils.getParseElement(sentence, parseName, addIfNotExist=True)
            if "treeline" in sentObj:
                parse.set("pennstring", sentObj["treeline"])
                counts["sentences-with-penn-tree" if sentObj["treeline"] != "" else "sentences-without-penn-tree"] += 1
            tokenization = None
            if "tokens" in sentObj or "dependencies" in sentObj:
                if tokenizerName != None: # Check for existing tokenization
                    tokenization = IXMLUtils.getTokenizationElement(sentence, tokenizerName, addIfNotExist=False, mustNotExist=False)
                if tokenization == None: # Parser-generated tokens
                    tokenization = IXMLUtils.getTokenizationElement(sentence, parseName, addIfNotExist=True, mustNotExist=True)
            if "tokens" in sentObj:
                if tokenization.find("token") == None:
                    self.insertTokens(sentObj["tokens"], sentence, tokenization, counts=counts)
                else:
                    self.mapTokens(sentObj["tokens"], sentence, tokenization, counts=counts)
            #if "dependencies" in sentObj or "phrases" in sentObj:
            #    parse = IXMLUtils.getParseElement(sentence, parseName, addIfNotExist=True)
            if "dependencies" in sentObj:
                self.insertDependencies(sentObj["dependencies"], sentence, parse, tokenization if tokenizerName != "LINKED" else "LINKED", counts=counts)
            if "phrases" in sentObj:
                self.insertPhrases(sentObj["phrases"], parse, sentObj["tokens"])
            if "metadata" in sentObj:
                self.insertMetadata(sentObj["metadata"], parse)
        return counts
    
    ###########################################################################
    # Sentence Splitting
    ###########################################################################
    
    def makeSentenceElement(self, document, offset, sentences):
        assert offset[1] > offset[0]
        # Make sentence element
        docText = document.get("text")
        e = ET.Element("sentence")
        e.set("id", document.get("id") + ".s" + str(len(sentences)))
        e.set("text", docText[offset[0]:offset[1]])
        e.set("charOffset", str(offset[0]) + "-" + str(offset[1]))
        # Set tail string for previous sentence
        if len(sentences) > 0:
            prevSentence = sentences[-1]
            prevEnd = int(prevSentence.get("charOffset").split("-")[1])
            if offset[0] - prevEnd > 1:
                prevSentence.set("tail", docText[prevEnd + 1:offset[0]])
        # Set head string for first sentence in document
        if offset[0] > 0 and prevSentence == None:
            e.set("head", docText[0:offset[0]])
        sentences.append(e)
        
    def splitSentences(self, sentObjs, document, counter=None, counts=None):
        docText = document.get("text")
        if docText.strip() == "": # Document has no text
            return
        if len([x for x in document if x.tag == "sentence"]) != 0:
            raise Exception("Cannot split sentences (document already has child elements).")
        # Collect tokens from all sentence object and mark their sentence index in them
        removeWhitespacePattern = re.compile(r'\s+')
        tokenTexts = []
        tokenSentences = []
        for i in range(len(sentObjs)):
            for token in sentObjs[i].get("tokens", []):
                tokenSentences.append(i)
                tokenText = token["text"]
                tokenText = re.sub(removeWhitespacePattern, '', tokenText)
                tokenTexts.append(tokenText)
        docTokens = []
        docTokenOffsets = []
        docPos = 0
        for docToken in re.split(r'(\s+)', docText):
            if not docToken.isspace():
                docTokens.append(docToken)
                docTokenOffsets.append((docPos, docPos + len(docToken)))
            docPos += len(docToken)
        
        tokenMatches = []
        for tokenText in tokenTexts:
            matches = [i for i in range(len(docTokens)) if docTokens[i] == tokenText]
            if tokenText in self.escDict:
                unescaped = self.escDict[tokenText]
                matches += [i for i in range(len(docTokens)) if docTokens[i] == unescaped]
            tokenMatches.append(matches)
        window = 10
        bestMatches = []
        for i in range(len(tokenMatches)):
            bestScore = 999999
            bestCandidate = None
            if len(tokenMatches[i]) > 0:
                for candidate in tokenMatches[i]:
                    candScore = 0
                    for j in range(i, i - window):
                        lower = [candidate - x for x in tokenMatches[j] if x < candidate]
                        if len(lower) > 0:
                            candScore += min(lower)
                    for j in range(i, i - window):
                        higher = [x - candidate for x in tokenMatches[j] if x > candidate]
                        if len(higher) > 0:
                            candScore += min(higher)
                    if candScore < bestScore:
                        bestScore = candScore
                        bestCandidate = candidate
                bestMatches.append(bestCandidate)
            else:
                bestMatches.append(None)
        print tokenTexts
        print docTokens
        print tokenMatches
        print "BEST", bestMatches
        print "COMP", [(tokenTexts[i], bestMatches[i]) for i in range(len(tokenTexts))]    
        sys.exit()
                    
                    
                        
        
            
        tokenAlignments = self.alignTokens(tokenTexts, docTokens, debugMessage=None)
        if counts == None:
            counts = defaultdict(int)
        if isinstance(counter, basestring):
            counter = ProgressCounter(len(tokenAlignments), counter)
        currentSentence = None #{"begin":None, "index":0}
        sentences = []
        for i in range(len(tokenAlignments)):
            counts["tokens-total"] += 1
            if counter:
                counter.update(1, "Processing token " + str(i) + " for sentence index " + str(tokenSentences[i]) + ": ")
            sentenceIndex = tokenSentences[i]
            docTokenIndex = tokenAlignments[i]
            if docTokenIndex != None:
                offset = docTokenOffsets[docTokenIndex]
                if currentSentence == None or sentenceIndex != currentSentence["index"]: # Start a new sentence
                    if currentSentence != None: # Make an element for the current sentence
                        self.makeSentenceElement(document, currentSentence["offset"], sentences)
                    currentSentence = {"offset":[min(offset), max(offset)+1], "index":sentenceIndex} # Start a sentence from the first aligned character
                else: # Extend current sentence
                    currentSentence["offset"][1] = max(offset) + 1
                counts["tokens-aligned"] += 1
            else:
                counts["tokens-not-aligned"] += 1
        if currentSentence != None: # and alignedCharOffset > currentSentence["begin"]:
            self.makeSentenceElement(document, currentSentence["offset"], sentences)
        for sentence in sentences:
            document.append(sentence)
            counts["new-sentences"] += 1
        GeniaSentenceSplitter.moveElements(document)
        return counts
    
#     def splitSentences(self, sentObjs, document, counter=None, counts=None):
#         docText = document.get("text")
#         if docText.strip() == "": # Document has no text
#             return
#         if len([x for x in document if x.tag == "sentence"]) != 0:
#             raise Exception("Cannot split sentences (document already has child elements).")
#         removeWhitespacePattern = re.compile(r'\s+')
#         docTokens = re.split(r'(\s+)', docText)
#         docTokenOffsets = []
#         docPos = 0
#         for docToken in docTokens:
#             docTokenOffsets.append((docPos, docPos + len(docToken)))
#             docPos += len(docToken)
#         docTokenIndex = 0
#         sentOffset = [0,0]
#         sentences = []
#         for i in range(len(sentObjs)):
#             for token in sentObjs[i].get("tokens", []):
#                 tokenText = token["text"]
#                 tokenText = re.sub(removeWhitespacePattern, '', tokenText)
#                 if tokenText != docTokens[docTokenIndex] and tokenText in self.escDict:
#                     tokenText = self.escDict[tokenText]
#                 if tokenText == docTokens[docTokenIndex]:
#                     sentOffset[1] = docTokenOffsets[docTokenIndex][1]
#                     docTokenIndex += 1
#             if sentOffset[0] != sentOffset[1]:
#                 self.makeSentenceElement(document, sentOffset, sentences)
#                 sentOffset = [sentOffset[1], sentOffset[1]]
#                 counts["new-sentences"] += 1
#             else:
#                 counts["unmatched-sentences"] += 1
#         for sentence in sentences:
#             document.append(sentence)
#         GeniaSentenceSplitter.moveElements(document)
#         return counts

#     def splitSentences(self, sentObjs, document, counter=None, counts=None):
#         docText = document.get("text")
#         if docText.strip() == "": # Document has no text
#             return
#         if len([x for x in document if x.tag == "sentence"]) != 0:
#             raise Exception("Cannot split sentences (document already has child elements).")
#         removeWhitespacePattern = re.compile(r'\s+')
#         if counts == None:
#             counts = defaultdict(int)
#         if isinstance(counter, basestring):
#             counter = ProgressCounter(len(sentObjs), counter)
#         docTokens = document.get("text").split()
#         docTextPos = 0
#         sentences = []
#         for i in range(len(sentObjs)):
#             if counter:
#                 counter.update(1, "Processing sentence " + str(i) + ": ")
#             tokens = sentObjs[i].get("tokens", [])
#             tokenTexts = [re.sub(removeWhitespacePattern, '', x["text"]) for x in tokens]
#             tokenAlignments = []
#             tokenTextLength = sum([len(x) for x in tokenTexts])
#             if tokenTextLength > 0:
#                 docSpan = docText[docTextPos:docTextPos + 2 * tokenTextLength + len(tokenTexts)]
#                 tokenAlignments = self.alignStrings(tokenTexts, docSpan, "", removeWhitespacePattern, document.get("id") + "/" + str(i), "Partial alignment in sentence splitting for document")
#                 tokenAlignments = [x for x in tokenAlignments if x != None]
#             if len(tokenAlignments) > 0:
#                 sentenceOffset = (docTextPos + min([x[0] for x in tokenAlignments]), docTextPos + max([x[1] for x in tokenAlignments]))
#                 docTextPos = sentenceOffset[1]
#                 self.makeSentenceElement(document, sentenceOffset, sentences)
#                 counts["sentences-aligned"] += 1
#             else:
#                 counts["sentences-not-aligned"] += 1
#         for sentence in sentences:
#             document.append(sentence)
#             counts["new-sentences"] += 1
#         GeniaSentenceSplitter.moveElements(document)
#         return counts

#     def splitSentences(self, sentObjs, document, counter=None, counts=None):
#         docText = document.get("text")
#         if docText.strip() == "": # Document has no text
#             return
#         if len([x for x in document if x.tag == "sentence"]) != 0:
#             raise Exception("Cannot split sentences (document already has child elements).")
#         removeWhitespacePattern = re.compile(r'\s+')
#         if counts == None:
#             counts = defaultdict(int)
#         if isinstance(counter, basestring):
#             counter = ProgressCounter(len(sentObjs), counter)
#         docText = document.get("text")
#         docTextPos = 0
#         sentences = []
#         for i in range(len(sentObjs)):
#             if counter:
#                 counter.update(1, "Processing sentence " + str(i) + ": ")
#             tokens = sentObjs[i].get("tokens", [])
#             tokenTexts = [re.sub(removeWhitespacePattern, '', x["text"]) for x in tokens]
#             tokenAlignments = []
#             tokenTextLength = sum([len(x) for x in tokenTexts])
#             if tokenTextLength > 0:
#                 docSpan = docText[docTextPos:docTextPos + 2 * tokenTextLength + len(tokenTexts)]
#                 tokenAlignments = self.alignStrings(tokenTexts, docSpan, "", removeWhitespacePattern, document.get("id") + "/" + str(i), "Partial alignment in sentence splitting for document")
#                 tokenAlignments = [x for x in tokenAlignments if x != None]
#             if len(tokenAlignments) > 0:
#                 sentenceOffset = (docTextPos + min([x[0] for x in tokenAlignments]), docTextPos + max([x[1] for x in tokenAlignments]))
#                 docTextPos = sentenceOffset[1]
#                 self.makeSentenceElement(document, sentenceOffset, sentences)
#                 counts["sentences-aligned"] += 1
#             else:
#                 counts["sentences-not-aligned"] += 1
#         for sentence in sentences:
#             document.append(sentence)
#             counts["new-sentences"] += 1
#         GeniaSentenceSplitter.moveElements(document)
#         return counts
    
#     def splitSentencesOld(self, sentObjs, document, counter=None, counts=None):
#         docText = document.get("text")
#         if docText.strip() == "": # Document has no text
#             return
#         if len([x for x in document if x.tag == "sentence"]) != 0:
#             raise Exception("Cannot split sentences (document already has child elements).")
#         # Collect tokens from all sentence object and mark their sentence index in them
#         #tokens = []
#         #tokenChars = ""
#         #tokenCharSentences = []
#         removeWhitespacePattern = re.compile(r'\s+')
#         tokenTexts = []
#         tokenSentences = []
#         for i in range(len(sentObjs)):
#             for token in sentObjs[i].get("tokens", []):
#                 tokenSentences.append(i)
#                 #token["sentenceIndex"] = i
#                 #tokens.append(token)
#                 tokenText = token["text"]
#                 tokenText = re.sub(removeWhitespacePattern, '', tokenText)
#                 tokenTexts.append(tokenText)
#                 #tokenCharSentences.extend([i] * len(tokenText))
#                 #tokenChars += tokenText
#         tokenAlignments = self.alignStrings(tokenTexts, docText, "", removeWhitespacePattern, document.get("id"), "Partial alignment in sentence splitting for document")
# #         # Split the document text into words and define their character offsets
# #         docChars = ""
# #         docCharOffsets = []
# #         for i in range(len(docText)): #re.split(r'(\s+)', docText):
# #             if not docText[i].isspace(): #if span.strip() != "":
# #                 docChars += docText[i]
# #                 docCharOffsets.append(i) #((i, i + 1))
#         # Align tokens agains document words
#         #print [docChars, tokenChars]
# #         alignedSentence, alignedCat, diff, alignedOffsets = Align.align(docChars, tokenChars)
# #         if diff.count("|") + diff.count("-") != len(diff):
# #             print >> sys.stderr, "Partial alignment in sentence splitting for document", document.get("id")
# #             Align.printAlignment(alignedSentence, alignedCat, diff)
#         # Initialize counters
#         if counts == None:
#             counts = defaultdict(int)
#         if isinstance(counter, basestring):
#             counter = ProgressCounter(len(tokenAlignments), counter)
#         # Use the aligned tokens to generate sentence elements
#         #currentSentIndex = 0
#         #currentSentBegin = -1
#         currentSentence = None #{"begin":None, "index":0}
#         sentences = []
#         for i in range(len(tokenAlignments)):
#             counts["tokens-total"] += 1
#             if counter:
#                 counter.update(1, "Processing token " + str(i) + " for sentence index " + str(tokenSentences[i]) + ": ")
#             sentenceIndex = tokenSentences[i]
#             #token = tokens[i]
#             docCharIndices = tokenAlignments[i]
#             if docCharIndices != None:
#                 #alignedCharOffset = docCharOffsets[docCharIndex]
#                 if currentSentence == None or sentenceIndex != currentSentence["index"]: # Start a new sentence
#                     if currentSentence != None: # Make an element for the current sentence
#                         self.makeSentenceElement(document, currentSentence["offset"], sentences)
#                     currentSentence = {"offset":[min(docCharIndices), max(docCharIndices)+1], "index":sentenceIndex} # Start a sentence from the first aligned character
#                 else: # Extend current sentence
#                     currentSentence["offset"][1] = max(docCharIndices) + 1
#                 counts["tokens-aligned"] += 1
#             else:
#                 counts["tokens-not-aligned"] += 1
#         if currentSentence != None: # and alignedCharOffset > currentSentence["begin"]:
#             self.makeSentenceElement(document, currentSentence["offset"], sentences)
#         for sentence in sentences:
#             document.append(sentence)
#             counts["new-sentences"] += 1
#         GeniaSentenceSplitter.moveElements(document)
#         return counts
    
    ###########################################################################
    # Penn Tree File Processing
    ###########################################################################
                
    def insertPennTrees(self, treeFileName, corpusRoot, parseName, requireEntities=False, skipIds=[], skipParsed=True):
        print >> sys.stderr, "Inserting parses"
        #counts = defaultdict(int)
        #extraAttributes = self.getExtraAttributes("const")
        #treeFile = codecs.open(treeFileName, "rt", "utf-8")
        sentObjs = self.readPennTrees(treeFileName)
        sentences = [x for x in self.getSentences(corpusRoot, requireEntities, skipIds, skipParsed)]
        #counter = ProgressCounter(len(sentences), "Penn Tree Insertion")
        counts = self.insertElements(sentObjs, sentences, parseName, counter="Penn Tree Insertion")
        #for sentence in sentences:
        #    counter.update(1, "Inserting parse for (" + sentence.get("id") + "): ")
        #    treeLine = treeFile.readline()
        #    self.insertPennTree(sentence, treeLine, parseName, makePhraseElements=makePhraseElements, extraAttributes=extraAttributes, counts=counts)
        #    counts["sentences"] += 1
        #treeFile.close()
        # Show statistics
        print >> sys.stderr, "Penn parse statistics:", dict(counts)
        print >> sys.stderr, "Parsed", counts["sentences"], "sentences"
        if counts["sentences-without-penn-tree"] == 0:
            print >> sys.stderr, "All sentences had a Penn tree"
        else:
            print >> sys.stderr, "Warning, no penn tree for", counts["sentences-without-penn-tree"], "out of", counts["sentences"], "sentences"
            print >> sys.stderr, "The \"pennstring\" attribute of these sentences has an empty string."  
        return counts
    
#     def insertPennTree(self, sentence, treeLine, parserName="McCC", tokenizerName = None, extraAttributes={}, counts=None, makePhraseElements=True, docId=None):
#         tokens, phrases = None, None
#         treeLine = treeLine.strip()
#         # First add the tokenization element
#         if treeLine == "":
#             counts["sentences-without-penn-tree"] += 1
#         else:
#             tokens, phrases = self.readPennTree(treeLine, sentence.get("id"))
#             tokenization = None
#             if tokenizerName != None: # Check for existing tokenization
#                 tokenization = IXMLUtils.getTokenizationElement(sentence, tokenizerName, addIfNotExist=False, mustNotExist=False)
#             if tokenization == None: # Parser-generated tokens
#                 tokenization = IXMLUtils.getTokenizationElement(sentence, parserName, addIfNotExist=True, mustNotExist=True)
#                 for attr in sorted(extraAttributes.keys()): # add the parser extra attributes to the parser generated tokenization 
#                     tokenization.set(attr, extraAttributes[attr])
#                 self.insertTokens(tokens, sentence, tokenization, counts=counts)
#             else:
#                 self.alignTokens(tokens, sentence, tokenization, counts=counts)
#             counts["sentences-with-penn-tree"] += 1
#         # Then add the parse element
#         parse = IXMLUtils.getParseElement(sentence, parserName, addIfNotExist=True, mustNotExist=True)
#         parse.set("pennstring", treeLine)
#         for attr in sorted(extraAttributes.keys()):
#             parse.set(attr, extraAttributes[attr])
#         # Insert phrases to the parse
#         if makePhraseElements and phrases != None:
#             self.insertPhrases(phrases, parse, tokens)
    
    def readPennTrees(self, treeFileName):
        sentObjs = []
        with codecs.open(treeFileName, "rt", "utf-8") as f:
            for line in f:
                treeLine = line.strip()
                tokens, phrases = self.readPennTree(treeLine)
                sentObjs.append({"tokens":tokens, "phrases":phrases, "treeline":treeLine})
        return sentObjs
    
    def readPennTree(self, treeLine): #, sentenceDebugId=None):
        tokens = []
        phrases = []
        stack = []
        treeLine = treeLine.strip()
        if treeLine != "":
            # Add tokens
            tokenCount = 0
            index = 0
            for char in treeLine:
                if char == "(":
                    stack.append( (index + 1, tokenCount) )
                elif char == ")":
                    span = treeLine[stack[-1][0]:index]
                    splits = span.split(None, 1) # span.split(string.whitespace)
                    if span.endswith(")"):
                        phrases.append({"begin":stack[-1][1], "end":tokenCount - 1, "type":splits[0]})
                    else:
                        #if len(splits) == 2:
                        origTokenText = splits[1]
                        tokenText = self.unescape(origTokenText).strip()
                        pos = self.unescape(splits[0])
                        tokens.append({"text":tokenText, "POS":pos, "origText":origTokenText, "index":tokenCount})
                        #else:
                        #    print >> sys.stderr, "Warning, unreadable token '", repr(span), "' in", sentenceDebugId
                        tokenCount += 1
                    stack.pop()
                index += 1
        return tokens, phrases
    
    ###########################################################################
    # Stanford Dependency Parse File Processing
    ###########################################################################
    
    def insertStanfordDependencyParses(self, depFilePath, corpusRoot, parseName, requireEntities=False, skipIds=[], skipParsed=True, skipExtra=0, removeExisting=False):
        #counts = defaultdict(int)
        #extraAttributes = self.getExtraAttributes("dep", extraAttributes)
        #depFile = codecs.open(depFilePath, "rt", "utf-8")
        sentObjs = self.readStanfordDependencies(depFilePath)
        sentences = [x for x in self.getSentences(corpusRoot, requireEntities, skipIds, skipParsed)]
        counts = self.insertElements(sentObjs, sentences, parseName, parseName, counter="Dependency Parse Insertion")
        #sentences = []
        #for document in corpusRoot.findall("document"):
        #    for sentence in document.findall("sentence"):
        #        sentences.append(sentence)
        #counter = ProgressCounter(len(sentences), "Dependency Parse Insertion")
        #for sentence in sentences:
        #    counter.update(1, "Inserting parse for (" + sentence.get("id") + "): ")
        #    self.insertDependencyParse(sentence, depFile, parseName, None, extraAttributes, counts, skipExtra=skipExtra, removeExisting=removeExisting)
        #depFile.close()
        print >> sys.stderr, "Dependency parse statistics:", dict(counts)
        if counts["deps-total"] == counts["deps-elements"]:
            print >> sys.stderr, "All dependency elements were aligned"
        else:
            print >> sys.stderr, "Warning,", counts["deps-total"] - counts["deps-elements"], "dependencies could not be aligned"
        
#     def insertDependencyParse(self, sentence, depFile, parserName="McCC", tokenizerName = None, extraAttributes={}, counts=None, skipExtra=0, removeExisting=False):
#         deps = self.readDependencies(depFile, skipExtra, sentence.get("id"))
#         # Initialize the parse element
#         parse = IXMLUtils.getParseElement(sentence, parserName, addIfNotExist=True)
#         if len(parse.findall("dependency")) > 0:
#             if removeExisting: # Remove existing dependencies
#                 for dependency in parse.findall("dependency"):
#                     parse.remove(dependency)
#             else: # don't reparse
#                 if counts != None: counts["existing-dep-parse"] += 1
#                 return
#         if parse.get("pennstring") in (None, ""):
#             parse.set("dep-parse", "no penn")
#             if counts != None: counts["no-penn"] += 1
#             return
#         for attr in sorted(extraAttributes.keys()):
#             parse.set(attr, extraAttributes[attr])
#         # Add the dependencies
#         if tokenizerName == None:
#             tokenizerName = parserName
#         tokenization = IXMLUtils.getTokenizationElement(sentence, tokenizerName, addIfNotExist=False)        
#         elements = self.insertDependencies(deps, sentence, parse, tokenization, counts=counts)
#         parse.set("dep-parse", "no dependencies" if (len(elements) == 0) else "ok")
#         counts["sentences"] += 1
#         return elements
    
    def readStanfordDependencies(self, depFilePath): #, skipExtra=0, sentenceId=None):
        sentences = []
        with codecs.open(depFilePath, "rt", "utf-8") as f:
            deps = None
            for line in f:
                line = line.strip()
                ## BioNLP'09 Shared Task GENIA uses _two_ newlines to denote a failed parse (usually it's one,
                ## the same as the BLLIP parser. To survive this, skipExtra can be used to define the number
                ## of lines to skip, if the first line of a dependency parse is empty (indicating a failed parse) 
                #if line.strip() == "" and skipExtra > 0:
                #    for i in range(skipExtra):
                #        depFile.readline()
                if line == "":
                    if deps != None:
                        sentences.append({"dependencies":deps})
                        deps = None # End the current sentence
                    else: # Extra empty lines indicate a failed parse
                        sentences.append({"dependencies":[]})
                else:
                    if deps == None: # Begin a new sentence
                        deps = []
                    depType = t1 = t2 = t1Word = t2Word = t1Index = t2Index = None
                    try:
                        depType, rest = line[:-1].split("(", 1)
                        t1, t2 = rest.split(", ")
                        t1Word, t1Index = t1.rsplit("-", 1)
                        t1Word = self.unescape(t1Word).strip()
                        while not t1Index[-1].isdigit(): t1Index = t1Index[:-1] # invalid literal for int() with base 10: "7'"
                        t1Index = int(t1Index) - 1
                        t2Word, t2Index = t2.rsplit("-", 1)
                        t2Word = self.unescape(t2Word).strip()
                        while not t2Index[-1].isdigit(): t2Index = t2Index[:-1] # invalid literal for int() with base 10: "7'"
                        t2Index = int(t2Index) - 1
                        if t1Word != "DUMMYINPUTTOKEN" and t2Word != "DUMMYINPUTTOKEN":
                            deps.append({"type":depType, "t1Word":t1Word, "t1":t1Index, "t2Word":t2Word, "t2":t2Index})
                    except Exception as e:
                        print >> sys.stderr, e
                        print >> sys.stderr, "Warning, unreadable dependency '", line.strip(), "', in sentence", len(sentences), [depType, t1, t2, (t1Word, t1Index), (t2Word, t2Index)], depFilePath
            if deps != None:
                sentences.append({"dependencies":deps})
        return sentences
    
    ###########################################################################
    # CoNLL File Processing
    ###########################################################################
    
    def getCoNLLFormat(self, inPath=None, conllFormat=None):
        if conllFormat == None:
            assert inPath != None
            ext = inPath.rsplit(".", 1)[-1]
            if ext in ("conll", "conllx"):
                conllFormat = "conllx"
            elif ext == "conllu":
                conllFormat = "conllu"
            elif ext == "corenlp":
                conllFormat = "corenlp"
        if conllFormat == "conll":
            conllFormat = "conllx"
        assert conllFormat in ("conllx", "conllu", "corenlp"), conllFormat
        return conllFormat
    
    def getCoNLLColumns(self, inPath=None, conllFormat=None):
        assert inPath != None or conllFormat != None
        conllFormat = self.getCoNLLFormat(inPath, conllFormat)
        if conllFormat == "conllx":
            return ["ID", "FORM", "LEMMA", "CPOSTAG", "POSTAG", "FEATS", "HEAD", "DEPREL", "PHEAD", "PDEPREL"]
        elif conllFormat == "corenlp": # Official column names are wordIndex, token, lemma, POS, NER, head, depRel
            return ["ID", "FORM", "LEMMA", "POS", "NER", "HEAD", "DEPREL"]
        else:
            return ["ID", "FORM", "LEMMA", "UPOSTAG", "XPOSTAG", "FEATS", "HEAD", "DEPREL", "DEPS", "MISC"]
    
    def readCoNLL(self, inPath, conllFormat=None):
        columns = self.getCoNLLColumns(inPath, conllFormat)
        sentence = None
        sentences = []
        with codecs.open(inPath, "rt", "utf-8") as f:
            for line in f:
                line = line.strip()
                if line == "":
                    if sentence == None: # Additional empty line
                        sentences.append({"words":[], "metadata":[]})
                    sentence = None
                else:
                    if sentence == None:
                        sentence = {"words":[], "metadata":[]}
                        sentences.append(sentence)
                    if line.startswith("#"): # A metadata line
                        sentence["metadata"].append(line)
                    else:
                        splits = line.split("\t")
                        assert len(splits) == len(columns), (splits, columns)
                        word = {columns[i]:splits[i] for i in range(len(columns))}
                        sentence["words"].append(word)
        return sentences
    
    def processCoNLLSentences(self, sentences, unescaping=False):
        outSentences = []
        for sentence in sentences:
            tokens = []
            dependencies = []
            tokenById = {}
            origIdsRequired = False
            # Build the tokens
            for i in range(len(sentence["words"])):
                word = sentence["words"][i]
                # Use the first available, non-underscore tag from the list as the token's POS tag
                pos = "_"
                for key in ("CPOSTAG", "POSTAG", "UPOSTAG", "XPOSTAG", "POS"):
                    if word.get(key, "_") != "_":
                        pos = word[key]
                        break
                # Define the token
                token = {"POS":pos}
                for key in word:
                    if key == "FORM":
                        token["text"] = word[key]
                        if unescaping:
                            token["text"] = self.unescape(token["text"])
                    elif key == "ID":
                        token["id"] = word[key]
                        if not origIdsRequired and not (token["id"].isdigit() and int(token["id"]) == i + 1):
                            origIdsRequired = True
                    elif key != "POS":
                        if isinstance(word[key], basestring):
                            token[key.lower()] = word[key]
                        else:
                            token[key.lower()] = str(word[key])
                token = {key:token[key] for key in token if token[key] != "_"}
                token["index"] = i
                tokenById[token["id"]] = token
                tokens.append(token)
            if origIdsRequired:
                for token in tokens:
                    token["origId"] = token["id"]
            # Build the dependencies
            for word in sentence["words"]:
                # The word is the second node for the dependency edge
                t2 = word["ID"]
                # Process the primary dependency
                t1 = word["HEAD"]
                if t1 == "_":
                    continue
                if t1.isdigit() and int(t1) == 0 and t1 not in tokenById:
                    #if word["DEPREL"] != "root":
                    #    raise Exception("Non-root dependency token + '" + str([t1,t2]) + "' for word " + str(word) + " in sentence " + str(sentence))
                    tokenById[word["ID"]]["root"] = word["DEPREL"]
                else:
                    if t1 not in tokenById or t2 not in tokenById:
                        raise Exception("Dependency token + '" + str([t1,t2]) + "' not defined for word " + str(word) + " in sentence " + str(sentence))
                    dependencies.append({"type":word["DEPREL"], "t1":t1, "t2":t2, "t1Token":tokenById[t1], "t2Token":tokenById[t2]})
                # Process secondary dependencies
                if "DEPS" in word and word["DEPS"] != "_":
                    for depString in word["DEPS"].strip().split("|"):
                        t1, depType = depString.split(":", 1)
                        if t1 not in tokenById or t2 not in tokenById:
                            raise Exception("Secondary dependency token + '" + str([t1,t2]) + "' not defined for word " + str(word) + " in sentence " + str(sentence))
                        dependencies.append({"type":depType, "t1":t1, "t2":t2, "t1Token":tokenById[t1], "t2Token":tokenById[t2], "secondary":"True"})
            outSentence = {"tokens":tokens, "dependencies":dependencies}
            if len(sentence["metadata"]) > 0:
                outSentence["metadata"] = []
                for line in sentence["metadata"]:
                    assert line[0] == "#"
                    line = line[1:].strip()
                    metadata = {"text":line}
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.rstrip()
                        if value[0] == " ":
                            value = value[1:]
                        metadata = {"type":key, "text":value}
                    outSentence["metadata"].append(metadata)
            outSentences.append(outSentence)
        return outSentences
    
#     def insertCoNLLSentences(self, sentObjs, sentences, parseName="McCC", skipExtra=0, removeExisting=False, counter=None, counts=None):
#         if counts == None:
#             counts = defaultdict(int)
#         #extraAttributes = self.getExtraAttributes("dep", extraAttributes)
#         assert len(sentObjs) == len(sentences), (len(sentObjs), len(sentences))
#         for objs, sentence in zip(sentObjs, sentences):
#             if counter:
#                 counter.update(1, "Inserting parse for (" + sentence.get("id") + "): ")
#             tokenization = IXMLUtils.getTokenizationElement(sentence, parseName, addIfNotExist=True)
#             self.insertTokens(objs["tokens"], sentence, tokenization, counts=counts)
#             parse = IXMLUtils.getParseElement(sentence, parseName, addIfNotExist=True)
#             self.insertDependencies(objs["dependencies"], sentence, parse, "linked", counts=counts)
#         return counts
    
    def insertCoNLLParses(self, coNLLFilePath, corpusRoot, parseName="McCC", extraAttributes=None, removeExisting=False, unescaping=False):
        sentRows = self.readCoNLL(coNLLFilePath)
        sentObjs = self.processCoNLLSentences(sentRows, unescaping=unescaping)
        sentences = [x for x in self.getSentences(corpusRoot, skipParsed=not removeExisting)]
        counter = ProgressCounter(len(sentences), "Dependency Parse Insertion")
        counts = defaultdict(int)
        self.insertElements(sentObjs, sentences, parseName, "LINKED", counts, counter)
        print >> sys.stderr, "CoNLL parse statistics:", dict(counts)
        if counts["deps-total"] == counts["deps-elements"]:
            print >> sys.stderr, "All dependency elements were aligned"
        else:
            print >> sys.stderr, "Warning,", counts["deps-total"] - counts["deps-elements"], "dependencies could not be aligned"
    
    ###########################################################################
    # EPE File Processing
    ###########################################################################
    
    def readEPE(self, inPath):
        sentences = []
        basicKeys = set(["form", "id", "properties", "edges", "text", "index", "POS", "pos", "start", "end"])
        with codecs.open(inPath, "rt", "utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                tokens = []
                tokenById = {}
                for node in obj["nodes"]:
                    properties = node.get("properties", {})
                    token = {"text":node["form"], "id":node["id"], "POS":properties.get("pos")}
                    for subset in node, properties:
                        for key in subset:
                            if key not in basicKeys:
                                if isinstance(subset[key], basestring):
                                    token[key.lower()] = subset[key]
                                else:
                                    token[key.lower()] = str(subset[key])
                    tokens["index"] = len(tokens)
                    tokens.append(token)
                    assert token["id"] not in tokenById
                    tokenById[token["id"]] = token
                dependencies = []
                for node in obj["nodes"]:
                    nodeId = node["id"]
                    edges = node.get("edges", [])
                    for edge in edges:
                        dependencies.append({"type":edge["label"], "t1":nodeId, "t2":edge["target"], "t1Token":tokenById[nodeId], "t2Token":tokenById[edge["target"]]})
                sentences.append({"tokens":tokens, "dependencies":dependencies})
        return sentences