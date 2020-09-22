import multiprocessing 
from tqdm import tqdm
import json
import math
import requests
import multiprocessing.pool
from bs4 import BeautifulSoup
import html2text

#Needed for proper formatting
html2text.BODY_WIDTH = 0
html2text.single_line_break = True
import lxml.html
from lxml import etree
import os.path
from os import path



SCORE_THRESH=1
COMMENT_SCORE_THRESH=-1
DESC_THRESH=1
PERCENT_TAKE = 0.5
HN_URL="https://hacker-news.firebaseio.com/v0/item/"
RANDOM_SEED=42


# Default Python Pool doesn't allow for daemon processes, if we want heirarchical pools
# we need to subclass Pool/Process since we need daemon processes
class NoDaemonProcess(multiprocessing.Process):
    # make 'daemon' attribute always return False
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

class MyPool(multiprocessing.pool.Pool):
    Process = NoDaemonProcess


# Story Functions

def get_check_story(id):
    """
    Checks if the id is a good story and starts the comment tree creating process 
    if need be
    """
    print(id)
    # Prevent recomputing 
    if path.exists(''.join(["data/",str(id)])):
        print("already did")
        return "already did"

    item = json.loads(requests.get(''.join([HN_URL, str(id),'.json'])).text) 
    
    # Some items might be dead, if they aren't the attribute usually isn't there
    # Use try/catch so we don't need to loop through all keys
    try:
        if item['dead'] == True:
            return "dead"
        pass
    except TypeError:
        return "nonexistant"
    except KeyError:
            pass

    # Good Story check
    try:
        if item['type'] != 'story': 
            print('story')
            return "not counted (not story)"
        if item['score'] < SCORE_THRESH:
            print('score')
            return "not counted (score too low)"
        if item['descendants'] < DESC_THRESH:
            print('len')
            return "not counted (num descenants too low)"
    except TypeError:
        print('type')
        return "not counted (typeerror)" 
    except KeyError:
        print('key')
        return "not counted (keyerror)"
    return parse_story(id,item)


def parse_story(id,item):
    """
        Creates the text representation of the story and starts the comment creation process
    """
    header = ''.join([item['title'],' - ',item['by'],'\n'])
    try:
        header = ''.join(['\n',header, item['url'], '\n'])
    except KeyError:
        pass
    try:
        header = ''.join(['\n',header, item['text'], '\n'])
    except KeyError:
        pass
    header = ''.join([header, '======'])

    
    comments = []
   
    #start comment chain creation in parallel
    commentpool = MyPool(12)
    comments = commentpool.map(top_comment_parse,item['kids'])
    commentpool.terminate()
    
    # Remove any blank strings in the result list (happens when a subcomment is dead)
    comments = list(filter(None, comments)) 
   # for comment in item['kids']:
   ##     parsed_comment = top_comment_parse(comment)
   ##     if parsed_comment != '':
   ##         comments.append(parsed_comment)

    #Add comments to story text
    comments = '------\n'.join(comments)
    header = ''.join([header, '\n', comments])


    # write to data/{id}
    with open(''.join(['data/',str(id)]),'w') as outfile:
        outfile.write(header)
    return header


# Comment Functions

def check_comment(item):
    """
    Decides if a comment is "good"
    """
    # For some reason some comments are blank
    try:
        if item['text'] == None:
            return False
    except KeyError:
        return False

    # Same "dead" attribute logic as with stories
    try:
        if item['dead'] == True :
            return False
    except KeyError:
        return True
    return True


def choose_next_sub_comment(comment_list):
    """
    Chooses the next coment based on a list of candidates,
    currently uses max_descendant
    """
    
    #take max descendant len
    def get_max_len(item):
        try:
            return len(item['kids'])
        except KeyError:
            return 0
    
    comment_list.sort(key= lambda x: get_max_len(x), reverse=True)
    return comment_list[0]

    #sort by score and take random one (not used but provided since I already wrote it)
    #comment_list.sort(key= lambda x: x['score'], reverse=True)
    #good_inds = math.ceil(PERCENT_TAKE * len(comment_list))
    #return random.choice(comment_list[:good_inds+1], seed=RANDOM_SEED)

def sub_comment_parse(item, comment_block):
    """
    Recursive function to parse comments and their subcomments
    """


# Past attempts at parsing, BS took too long and lxml didn't parse correctly
#    item['text'] = BeautifulSoup(item['text'], "lxml").get_text(separator="\n")
#    item['text'] = lxml.html.fromstring(item['text']).text_content()

    #extract html tags
    item['text'] = html2text.html2text(item['text'])
    comment_block = ''.join([comment_block, item['by'],'\n',item['text']])
    
    #return if no sub_comments
    try:
        if len(item['kids']) == 0:
            return comment_block
    except KeyError:
        return comment_block 

    #generate kid comment list
    kids = []
    for kid_id in item['kids']:
        kids.append(json.loads(requests.get(''.join([HN_URL, str(kid_id),'.json'])).text))
    possible_routes = [kid for kid in kids if check_comment(kid)]
    
    #kid comment(s) might be dead so the possible routes list might be empty (return since no good subcomment) 
    if len(possible_routes) == 0:
        return comment_block

    #choose next comment
    next_comment = choose_next_sub_comment(possible_routes)
    
    #Add to text representation and recurse
    comment_block = ''.join([comment_block, '~~~\n'])
    comment_block = sub_comment_parse(next_comment, comment_block)
    return comment_block

def top_comment_parse(id):
    """
    Retrieves the top-levle comment and starts the recursive sub-comment parsing
    """
    item = json.loads(requests.get(''.join([HN_URL, str(id),'.json'])).text) 
    comment_block = ''
    if check_comment(item):
        comment_block = sub_comment_parse(item, comment_block)
        #add top comment to the 
        #current_doc = ''.join([current_doc, item['by'],'\n',item['text']])
    return comment_block

        




def main(end_id):
    # map the list of lines into a list of result dicts
    pool = MyPool(12)
    resultlist = pool.map(get_check_story,range(1,end_id, 1))
    with open('resultlist','w') as result:
        result.write(resultlist)


if __name__ == "__main__":
    #get_check_story(200)
    print(main(10000000))
    #print(main(245317120))




