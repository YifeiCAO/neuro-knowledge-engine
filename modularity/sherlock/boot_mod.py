#!/usr/bin/python3

import pandas as pd
import numpy as np
np.random.seed(42)
from collections import OrderedDict
from scipy.spatial.distance import cdist
from utilities import *

def compute_boot(framework, version=190325, suffix="", n_iter=1000):

	# Load the data
	act_bin = load_coordinates()
	dtm_bin = load_doc_term_matrix(version=version, binarize=True)
	lists, circuits = load_framework(framework, suffix=suffix)
	words = sorted(list(set(lists["TOKEN"])))
	structures = sorted(list(set(act_bin.columns)))
	domains = list(OrderedDict.fromkeys(lists["DOMAIN"]))

	# Compute domain archetypes
	archetypes = pd.DataFrame(0.0, index=words+structures, columns=domains)
	for dom in domains:
		for word in lists.loc[lists["DOMAIN"] == dom, "TOKEN"]:
			archetypes.loc[word, dom] = 1.0
		for struct in structures:
			archetypes.loc[struct, dom] = circuits.loc[struct, dom]
	archetypes[archetypes > 0.0] = 1.0

	# Build document structure-term vectors
	pmids = dtm_bin.index.intersection(act_bin.index)
	dtm_words = dtm_bin.loc[pmids, words]
	act_structs = act_bin.loc[pmids, structures]
	docs = dtm_words.copy()
	docs[structures] = act_structs.copy()

	# Load document assignments
	doc2dom_df = pd.read_csv("../partition/data/doc2dom_{}.csv".format(framework), 
						 header=None, index_col=0)
	doc2dom = {int(pmid): int(dom) for pmid, dom in doc2dom_df.iterrows()}
	dom2docs = {dom: [] for dom in domains}
	for doc, dom in doc2dom.items():
		dom2docs[domains[dom-1]].append(doc)

	# Compute Dice distances
	doc_dists = cdist(docs, docs, metric="dice")
	doc_dists = pd.DataFrame(doc_dists, index=pmids, columns=pmids)

	# Sort Dice distances by document assignments
	sorted_pmids = []
	for dom in range(len(domains)):
		sorted_pmids += [pmid for pmid, sys in doc2dom.items() if sys == dom + 1]
	doc_dists = doc_dists[sorted_pmids].loc[sorted_pmids]

	# Compute domain min and max indices
	dom_idx = {dom: {"min": 0, "max": 0} for dom in domains}
	for dom in domains:
		dom_pmids = dom2docs[dom]
		dom_idx[dom]["min"] = sorted_pmids.index(dom_pmids[0])
		dom_idx[dom]["max"] = sorted_pmids.index(dom_pmids[-1]) + 1

	# Compute observed values
	dists_int, dists_ext = {}, {}
	for dom in domains:
		
		dom_min, dom_max = dom_idx[dom]["min"], dom_idx[dom]["max"]
		dom_dists = doc_dists.values[:,dom_min:dom_max][dom_min:dom_max,:]
		dists_int[dom] = dom_dists.ravel()
		
		other_dists_lower = doc_dists.values[:,dom_min:dom_max][:dom_min,:]
		other_dists_upper = doc_dists.values[:,dom_min:dom_max][dom_max:,:]
		other_dists = np.concatenate((other_dists_lower, other_dists_upper))
		dists_ext[dom] = other_dists.ravel()
		
	# Compute bootstrap distributions
	df_boot = np.empty((len(domains), n_iter))
	for n in range(n_iter):
		for i, dom in enumerate(domains):
			
			boot_int = np.random.choice(dists_int[dom], size=len(dists_int[dom]), replace=True)
			dist_int = np.nanmean(boot_int)
			
			boot_ext = np.random.choice(dists_ext[dom], size=len(dists_ext[dom]), replace=True)
			dist_ext = np.nanmean(boot_ext)
			
			df_boot[i,n] = dist_ext / dist_int
			
		if n % int(n_iter / 10.0) == 0:
			print("Processed {} iterations".format(n))

	# Export results
	file_boot = "data/mod_boot_{}_{}iter.csv".format(framework, n_iter)
	df_boot = pd.DataFrame(df_boot, index=domains, columns=range(n_iter))
	df_boot.to_csv(file_boot)

