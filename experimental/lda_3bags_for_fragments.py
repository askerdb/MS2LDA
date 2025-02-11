import sys
import timeit

from pandas.core.frame import DataFrame
from scipy.sparse import coo_matrix

from lda_3bags_for_fragments_viz import ThreeBags_Ms2Lda_Viz
from justin.lda_for_fragments import Ms2Lda
from lda_3bags_cgs import CollapseGibbs_3bags_Lda
import numpy as np
import pandas as pd
import pylab as plt


class ThreeBags_Ms2Lda(Ms2Lda):
    
    def run_lda(self, n_topics, n_samples, n_burn, n_thin, alpha, beta, 
                            use_native=True, previous_model=None):    
                        
        print "Fitting model with 3bags-LDA ..."
        self.n_topics = n_topics
        self.model = CollapseGibbs_3bags_Lda(self.df, self.vocab, n_topics, alpha, beta, previous_model=previous_model)
        self.n_topics = self.model.K # might change if previous_model is used

        start = timeit.default_timer()
        self.model.run(n_burn, n_samples, n_thin, use_native=use_native)
        stop = timeit.default_timer()
        print "DONE. Time=" + str(stop-start)        
                
    def write_results(self, results_prefix):

        previous_model = self.model.previous_model
        selected_topics = None
        if previous_model is not None and hasattr(previous_model, 'selected_topics'):
            selected_topics = previous_model.selected_topics
        
        # create topic words output for each bag
        self.topicdfs = []
        topic_bags = self.model.topic_word_
        for b in range(len(topic_bags)):
        
            # create topic-word output file
            # the column names of each topic is assigned here
            topic_names = []
            outfile = self._get_outfile(results_prefix, '_topics_bag' + str(b) + '.csv') 
            print "Writing topics to " + outfile
            topic_word = topic_bags[b]
            with open(outfile,'w') as f:
                
                counter = 0
                for i, topic_dist in enumerate(topic_word):

                    ordering = np.argsort(topic_dist)
                    vocab = self.data.columns.values                
                    topic_words = np.array(vocab)[ordering][::-1]
                    dist = topic_dist[ordering][::-1]
                    
                    if selected_topics is not None:
                        if i < len(selected_topics):
                            topic_name = 'Fixed Topic {}'.format(selected_topics[i])
                        else:
                            topic_name = 'Topic {}'.format(counter)
                            counter += 1
                    else:
                        topic_name = 'Topic {}'.format(i)                    
                    f.write(topic_name)
                    topic_names.append(topic_name)
                    
                    # filter entries to display by epsilon
                    for j in range(len(topic_words)):
                        if dist[j] > self.EPSILON:
                            f.write(',{}'.format(topic_words[j]))
                        else:
                            break
                    f.write('\n')

            # also create the topic-terms df    
            topic = topic_bags[b]    
            outfile = self._get_outfile(results_prefix, '_all_bag' + str(b) + '.csv') 
            print "Writing fragments x topics to " + outfile

            masses = np.array(self.df.transpose().index)
            d = {}
            for i in np.arange(self.n_topics):
                topic_name = topic_names[i]
                topic_series = pd.Series(topic[i], index=masses)
                d[topic_name] = topic_series
            topicdf = pd.DataFrame(d)
        
            # make sure that columns in topicdf are in the correct order
            # because many times we'd index the columns in the dataframes directly by their positions
            cols = topicdf.columns.tolist()
            sorted_cols = self._natural_sort(cols)
            topicdf = topicdf[sorted_cols]        
    
            # threshold topicdf to get rid of small values
            def f(x):
                if x < self.EPSILON: return 0
                else: return x
            topicdf = topicdf.applymap(f)
            topicdf.to_csv(outfile)
            self.topicdfs.append(topicdf)
    
        # create topic-docs output file
        doc = self.model.doc_topic_
        (n_doc, a) = doc.shape
        topic_index = np.arange(self.n_topics)
        doc_names = np.array(self.df.index)
        d = {}
        for i in np.arange(n_doc):
            doc_name = doc_names[i]
            doc_series = pd.Series(doc[i], index=topic_index)
            d[doc_name] = doc_series
        self.docdf = pd.DataFrame(d)
        
        # sort columns by mass_rt values
        cols = self.docdf.columns.tolist()
        mass_rt = [(float(m.split('_')[0]),float(m.split('_')[1])) for m in cols]
        sorted_mass_rt = sorted(mass_rt,key=lambda m:m[0])
        ind = [mass_rt.index(i) for i in sorted_mass_rt]
        self.docdf = self.docdf[ind]
        # self.docdf.to_csv(outfile)

        # threshold docdf to get rid of small values and also scale it
        self.docdf = self.docdf.applymap(f)                
        for i, row in self.docdf.iterrows(): # iterate through the rows
            doc = self.docdf.ix[:, i]
            selected = doc[doc>0]
            count = len(selected.values)
            selected = selected * count
            self.docdf.ix[:, i] = selected
        self.docdf = self.docdf.replace(np.nan, 0)
        outfile = self._get_outfile(results_prefix, '_docs.csv') 
        print "Writing topic docs to " + outfile
        self.docdf.transpose().to_csv(outfile)   
        
    def plot_lda_fragments(self, consistency=0.50, sort_by="h_index", selected_topics=None, interactive=False):
        plotter = ThreeBags_Ms2Lda_Viz(self.model, self.ms1, self.ms2, self.docdf, self.topicdfs, EPSILON=self.EPSILON)
        plotter.plot_lda_fragments(consistency=consistency, sort_by=sort_by, 
                                   selected_topics=selected_topics, interactive=interactive) 
        if interactive:
            self.model.visualise(plotter)                                           
    
def test_lda():

    if len(sys.argv)>1:
        n_topics = int(sys.argv[1])
    else:
        n_topics = 250
    n_samples = 200
    n_burn = 0
    n_thin = 1
    alpha = 50.0/n_topics
    beta = 0.1

    fragment_filename = '../input/relative_intensities/Beer_3_T10_POS_fragments_rel.csv'
    neutral_loss_filename = '../input/relative_intensities/Beer_3_T10_POS_losses_rel.csv'
    # mzdiff_filename = '../input/relative_intensities/Beer_3_T10_POS_mzdiffs_rel.csv'    
    mzdiff_filename = None

    ms1_filename = '../input/relative_intensities/Beer_3_T10_POS_ms1_rel.csv'
    ms2_filename = '../input/relative_intensities/Beer_3_T10_POS_ms2_rel.csv'
 
    ms2lda = ThreeBags_Ms2Lda.lcms_data_from_R(fragment_filename, neutral_loss_filename, mzdiff_filename, 
                                               ms1_filename, ms2_filename, vocab_type=2)
    ms2lda.run_lda(n_topics, n_samples, n_burn, n_thin, alpha, beta)
    ms2lda.write_results('beer3pos_alternative')
    ms2lda.plot_lda_fragments(consistency=0.50)    
            
def main():    
    test_lda()
    
if __name__ == "__main__": main()