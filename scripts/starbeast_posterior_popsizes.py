#! /usr/bin/env python
## This file is part of biopy.
## Copyright (C) 2010 Joseph Heled
## Author: Joseph Heled <jheled@gmail.com>
## See the files gpl.txt and lgpl.txt for copying conditions.

from __future__ import division

import optparse, sys, os.path

from numpy import mean, median
from scipy.optimize import fmin_powell

from biopy.genericutils import fileFromName

from biopy import INexus, beastLogHelper, demographic
from biopy.treeutils import toNewick, countNexusTrees, getTreeClades

parser = optparse.OptionParser(usage =
                               """ %prog [OPTIONS] tree posterior-trees.nexus.

	Annotate tree with posterior estimate of population sizes. Prints newick
	tree to standard output. On UNIX it is easy to get the tree for the
	first argument using biopy, e.g (using bash)
        starbeast_posterior_popsizes `summary_tree.py trees.nexus` trees.nexus.""")

parser.add_option("-b", "--burnin", dest="burnin",
                  help="Burn-in amount (percent, default %default)", default = "10")

parser.add_option("-e", "--every", dest="every", metavar="E",
                  help="""thin out - take one tree for every E. Especially
                  useful if you run out of memory (default all,
                  i.e. %default)""", default = "1")  

## parser.add_option("-o", "--optimizeTaxa", dest="optTaxa",
##                   help="Optimize population size at time 0 - default is to fix
##                   it at mean posterior value.",
##                   action="store_true", default = False)

parser.add_option("-p", "--progress", dest="progress",
                  help="Print out progress messages to terminal (standard error)",
                  action="store_true", default = False)

options, args = parser.parse_args()

progress = options.progress
every = int(options.every)
burnIn =  float(options.burnin)/100.0

if len(args) != 2 :
  parser.print_help(sys.stderr)
  sys.exit(1)
  
treeText, nexusTreesFileName = args[:2]

target = INexus.Tree(treeText)

targetClades = getTreeClades(target, True)

cladesDict = dict()
  
for c,n in targetClades:
  cladesDict[frozenset(c)] = []

noTaxaOpt = True ; # not options.optTaxa
if noTaxaOpt :
  taxaDict = dict([(tx,[]) for tx in target.get_taxa()])

try :
  nexFile = fileFromName(nexusTreesFileName)
except Exception,e:
  # report error
  print >> sys.stderr, "Error:", e.message
  sys.exit(1)

if progress:
  print >> sys.stderr, "counting trees ...,",
  
nTrees = countNexusTrees(nexusTreesFileName)

nexusReader = INexus.INexus()

if progress:
  print >> sys.stderr, "reading %d trees ...," % int((nTrees * (1-burnIn) / every)),

# Root 'branches'
rBranches = []

for tree in nexusReader.read(nexFile, slice(int(burnIn*nTrees), -1, every)):
  has = beastLogHelper.setDemographics([tree])         ; assert has[0]
  clades = getTreeClades(tree, True)
    
  for c,node in clades:
    cladeSet = frozenset(c)
    e = cladesDict.get(cladeSet)
    if e is not None :
      d = node.data.demographic
      l = d.naturalLimit()
      if l is None :
        ipop = 1/d.population(0)
      else :
        if node.id == tree.root :
          rBranches.append(l)
        ipop = node.data.demographic.integrate(l)/l
      e.append(ipop)
      if noTaxaOpt and len(cladeSet) == 1 :
        taxaDict[iter(cladeSet).next()].append( node.data.demographic.population(0))
        
constDemos = all([tree.node(x).data.demographic.naturalLimit() is None
                  for x in tree.all_ids()])

if constDemos :
  for ni in target.all_ids() :
    n = target.node(ni)
    vals = []
    for c,n1 in targetClades:
      if n == n1 :
        vals = cladesDict[frozenset(c)]      
        break
    if len(vals) :
      pop = 1/mean(vals)
      n.data.attributes = {'dmv' : '%g' % pop}
else :
  if progress:
    print >>  sys.stderr, "optimizing ...," ,

  tids = target.all_ids()
  tax = target.get_terminals()

  me = dict(zip(tids, range(len(tids))))
  ms = dict(zip(tax, range(len(tids), len(tids)+len(tax))))

  popIndices = []
  for ni in target.all_ids() :
    n = target.node(ni)
    pp = None
    if n.data.taxon :
      s = [ms[ni],None]
      if noTaxaOpt :
        pp = median(taxaDict[n.data.taxon])
    else :
      s = [me[x] for x in n.succ]
      
    b =  n.data.branchlength if ni != target.root else mean(rBranches)

    vals = []
    for c,n1 in targetClades:
      if n == n1 :
        vals = cladesDict[frozenset(c)]      
        break

    if len(vals) > 0 :
      v = (len(vals), sum(vals), sum([x**2 for x in vals]))
    else :
      v = (0,0,0)
    popIndices.append((s, me[ni], b, v, n, pp))

  def err(p, pasn) :
    pops = [abs(x) for x in p] 
    err = 0.0
    for (s1,s2),e,branch,(n,mn,smn),nd,pp in pasn :
      ps,pe = pops[s1] + (pops[s2] if s2 is not None else 0), pops[e]
      if pp is not None :
        ps = pp
      d = demographic.LinearPiecewisePopulation([ps,pe], [branch])
      ipop = d.integrate(branch)/branch
      xerr2 = n*ipop**2 - 2*ipop*mn + smn
      err += xerr2 * branch
    return err

  if 0 : # debug
    target.display()
    print [((s1,s2), e, branch, mn/n, (smn/n - (mn/n)**2)**.5,pp)
           for (s1,s2),e,branch,(n,mn,smn),nd,pp in popIndices]
    
  nTaxa = len(tax)
  nPopParams = 3*nTaxa - 1 # or 3n-1 or n
  pops = [1]*nPopParams

  oo = fmin_powell(lambda x : err(x, popIndices), pops, disp=0, full_output=1)
  pops = [abs(x) for x in oo[0]]

  for (s1,s2),e,branch,(n,mn,smn),nd,pp in popIndices :
    ps,pe = pops[s1] + (pops[s2] if s2 is not None else 0), pops[e]
    if pp is not None :
      ps = pp
    d = demographic.LinearPiecewisePopulation([ps,pe], [branch])
    ipop = d.integrate(branch)/branch
    if 0 :
      print (s1,s2),e, ipop, mn/n, (ps - d.population(0), ps, d.population(0))
      
    nd.data.attributes = {'dmv' : ('{%g,%g}' % (ps,pe)), 'dmt' : str(branch)}

if progress:
  print >>  sys.stderr, "done." 

print toNewick(target, attributes='attributes')  

