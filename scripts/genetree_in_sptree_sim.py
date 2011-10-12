#! /usr/bin/env python
## This file is part of biopy.
## Copyright (C) 2010 Joseph Heled
## Author: Joseph Heled <jheled@gmail.com>
## See the files gpl.txt and lgpl.txt for copying conditions.

from __future__ import division

import optparse, sys, os.path
parser = optparse.OptionParser("""%prog [OPTIONS] species-trees-file

  Generate gene trees compatible with species tree. The species
  trees in the NEXUS input file should contain population size
  information in the same format generated by *BEAST. Tips of
  invididuals belonging to 'species-name' are labeled
  'species-name_0', 'species-name_1', etc. in the gene tree.""")

parser.add_option("-n", "--ntrees", dest="ngenetrees",
                  help="""Number of gene trees per species tree """
                  + """(default 1)""", default = "1") 

parser.add_option("-t", "--per-species", dest="ntips",
                  help="""Number of individuals per species."""
                  + """(default 2)""", default = "2") 

parser.add_option("-o", "--nexus", dest="nexfile",
                  help="Print trees in nexus format to file", default = None)

parser.add_option("", "--total", dest="total",
                  help="""Stop after processing this number of species"""
                  + """ trees.""",
                  default = None) 

options, args = parser.parse_args()

nGeneTrees = int(options.ngenetrees) ; assert nGeneTrees > 0
nTips = int(options.ntips)           ; assert nTips > 0

nTotal = int(options.total) if options.total is not None else -1           

tipNameTemplate = "%s_tip%d"

nexusTreesFileName = args[0]

from biopy import INexus, speciesTreesGeneTrees, beastLogHelper, __version__
from biopy.treeutils import toNewick, TreeLogger
from biopy.genericutils import fileFromName

tlog = TreeLogger(options.nexfile, argv = sys.argv, version = __version__)

for tree in INexus.INexus().read(fileFromName(nexusTreesFileName)) :
  has = beastLogHelper.setDemographics([tree])
  
  if not has[0] :
    print >> sys.stderr, "No population size information in species tree"
    sys.exit(1)

  for tid in tree.get_terminals():
    data = tree.node(tid).data
    data.geneTreeTips = [tipNameTemplate % (data.taxon,k) for k in range(nTips)]
    
  for k in range(nGeneTrees) :
    g = speciesTreesGeneTrees.simulateGeneTree(tree)[0]

    tlog.outTree(toNewick(g))

  nTotal -= 1
  if nTotal == 0 :
    break
  
tlog.close()
