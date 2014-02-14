import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__))+"/../..")
import Utils.ElementTreeUtils as ETUtils
import subprocess
import SentenceElements
from Core.SentenceGraph import SentenceGraph

def getId(element, attribute="id"):
    return element.get(attribute).replace(".", "_");

def getHeadScore(token):
    headScore = 0
    if token.get("headScore") != None:
        headScore = int(token.get("headScore"))
    return headScore

def toGraphViz(input, output, id, parse="McCC"):
    print >> sys.stderr, "====== Making Graphs ======"
    xml = ETUtils.ETFromObj(input).getroot()
    sentence = None
    for document in xml.findall("document"):
        for s in document.findall("sentence"):
            if s.get("id") == id:
                sentence = s
                break
    if sentence == None:
        print >> sys.stderr, "No sentence for id", id
        return
    
    elements = SentenceElements.SentenceElements(sentence, parse)
    graph = SentenceGraph(elements.sentence, elements.tokens, elements.dependencies)
    graph.mapInteractions(elements.entities, elements.interactions)
    
    f = open(output, "wt")
    f.write("digraph " + id.replace(".", "_") + " {\n")
    #f.write("graph [label=\"Orthogonal edges\", splines=ortho, nodesep=0.1];\n")
    f.write("graph [nodesep=0.1];\n")
    f.write("node [shape=box];")
    f.write("ranksep=1;")
    
    f.write("subgraph tokens {\n")
    f.write("edge[weight=1000, arrowhead=none];\n")
    f.write("rankdir = LR;\n")
    f.write("rank=\"same\";\n")
    f.write("nodesep=0.01;\n")
    #f.write("{ rank=\"same\";\n")
    tokenIds = []
    for token in elements.tokens:
        tokenIds.append(token.get("id").replace(".", "_"))
        f.write(getId(token) + " [margin=0 label=\"" + token.get("text") + "\\n" + token.get("POS") + "\"];\n")
    f.write("->".join(tokenIds) + ";\n")
    f.write("}\n")
    
    f.write("subgraph dependencies {\n")
    #f.write("rank=\"same\";\n")
    #f.write("node [shape=ellipse margin=0];")
    f.write("edge[weight=0.001 color=green];\n")
    #f.write("{ rank=\"same\";\n")
    tokensByHeadScore = {}
    for token in elements.tokens:
        headScore = getHeadScore(token)
        if headScore not in tokensByHeadScore:
            tokensByHeadScore[headScore] = []
        tokensByHeadScore[headScore].append(token)
    depByHeadScore = {}
    depByHeadScore[0] = []
    for dep in elements.dependencies:
        f.write(getId(dep, "id") + " [margin=0 label=\"" + dep.get("type") + "\"];\n")
        f.write(getId(dep, "t1") + " -> " + getId(dep, "id") + " [weight=999];\n")
        f.write(getId(dep, "id") + " -> " + getId(dep, "t2") + " [weight=999];\n")
        token = graph.tokensById[dep.get("t1")]
        headScore = getHeadScore(token)
        if headScore not in depByHeadScore:
            depByHeadScore[headScore] = []
        depByHeadScore[headScore].append(getId(dep, "id"))
        
        
        #for i in range(headScore, -1, -1):
        #    for t in tokensByHeadScore[i]:
        #        f.write(getId(dep) + " -> " + getId(t) + ";\n")
        ##if token.get("headScore") != None and int(token.get("headScore")) > 0:
        ##    f.write(getId(dep, "id") + " -> " + token.get("headScore") + ";\n")
        #f.write(getId(dep, "t1") + " -> " + getId(dep, "t2") + ";\n")
    #for i in range(max(depByHeadScore.keys())+ 1):
    #    if i > 0:
    #        for d1 in depByHeadScore[i]:
    #            for d2 in depByHeadScore[i-1]:
    #                f.write(d1 + " -> " + d2 + " [weight=0.01 style=invis];\n")
    f.write("}\n")

    f.write("subgraph entities {\n")
    #f.write("rank=\"same\";\n")
    f.write("edge[weight=1];\n")
    #f.write("{ rank=\"same\";\n")
    for entity in elements.entities:
        if entity.get("event") != "True":
            f.write(getId(entity) + " [label=\"" + entity.get("type") + "\"];\n")
            headToken = graph.entityHeadTokenByEntity[entity]
            if headToken != None:
                f.write(getId(entity) + " -> " + getId(headToken) + ";\n")
        else:
            f.write(getId(entity) + " [label=\"" + entity.get("type") + "\"];\n")
    f.write("}\n")
    
    f.write("subgraph event_to_token {\n")
    f.write("edge[weight=1 color=blue];\n")
    for entity in elements.entities:
        if entity.get("event") == "True":
            headToken = graph.entityHeadTokenByEntity[entity]
            if headToken != None:
                f.write(getId(entity) + " -> " + getId(headToken) + ";\n")
    f.write("}\n")
    
    f.write("subgraph interactions {\n")
    for interaction in elements.interactions:
        f.write(getId(interaction, "e1") + " -> " + getId(interaction, "e2") + " [fontsize=8 label=\"" + interaction.get("type") + "\"];\n")
    f.write("}\n")
    
    f.write("}\n")
    f.close()
    subprocess.call("dot -Tpdf " + output + " > " + output + ".pdf", shell=True)
    

if __name__=="__main__":
    try:
        import psyco
        psyco.full()
        print >> sys.stderr, "Found Psyco, using"
    except ImportError:
        print >> sys.stderr, "Psyco not installed"
    from optparse import OptionParser
    optparser = OptionParser()
    optparser.add_option("-i", "--input", default=None, dest="input", help="input interaction XML file")
    optparser.add_option("-o", "--output", default=None, dest="output", help="output interaction XML file")
    optparser.add_option("-d", "--id", default=None, dest="id", help="sentence id")
    (options, args) = optparser.parse_args()
    
    toGraphViz(options.input, options.output, options.id)