from glob import glob
import json
import sys, time
import Levenshtein


# inf = open("../data/dialog-bAbI-tasks/artarin.txt")
# out = open("artarin2.txt", 'w')
# i = 0
# for line in inf.readlines():
#     i += 1
#     line = str(i)+" "+" ".join(line.split(" ")[1:])
#     out.write(line)


def is_request(word, ontology):
    if word in ontology['requestable']:
        return True, word
    else:
        return False, 'nope'


def has_word(word, ontology):
    lonto = []
    for elem in ontology['informable']['food']:
        lonto.append(elem)
    for elem in ontology['informable']['area']:
        lonto.append(elem)
    for elem in ontology['informable']['pricerange']:
        if elem == "moderately":
            elem = "moderate"
        lonto.append(elem)
    if word in lonto:
        return True
    else:
        return False


def negation(word, ontology):
    if word in ontology['informable']["negation"]:
        return True
    else:
        return False


def errors(dialogue, ontology, errors):
    apied = False  # pas encore appel api
    entities = []
    repeatedUser = {}
    repeatedSystem = {}
    turns = 0
    new = []
    for line in dialogue:
        if "<SILENCE>" in line:  # si l'utilisateur ne dit rien on est "gentil" avec le systeme
            new.append(line + '\n')
            inc = False
            continue
        
        if turns > 7:  # + de 7 tours de parole y a toujours un truc qui déconne
            inc = True
            errors += 1
        inc = False  # par défaut pas d'incohérence
        reason = ""
        line = line.rstrip()
        if 'api_call no result' in line or 'sorry' in line:
            apied = False
            entities = [elem for elem in entities if elem not in ontology['informable'][
                'food']]  # on garde les entités non liées à la bouffe (souvent ce que le user change dans ses requetes)
        if '\t' in line:
            
            turns += 1
            user = line.split('\t')[0].split(' ')[1:]
            user = " ".join(user)
            system = line.split('\t')[1]
            if user not in repeatedUser:
                repeatedUser[user] = [1, apied]
            else:  # si le user dit au moins 2x la même chose ERREUR
                if repeatedUser[user][1] == apied:
                    repeatedUser[user][0] += 1
                    reason = "several user"
                    inc = True
                    errors += 1
            if system not in repeatedUser:
                repeatedSystem[system] = [1, apied]
            else:  # si le system dit au moins 2x la même chose ERREUR
                if repeatedSystem[system][1] == apied:
                    repeatedSystem[system][0] += 1
                    reason = "several system"
                    inc = True
                    errors += 1
            if not apied:
                if "how about" in user or "and" in user:
                    entities = []
                for word in user.split():
                    if has_word(word, ontology):  # on rajoute les entités grace à l'ontologie
                        entities.append(word.replace(' ', '_'))
                        print(entities)
            if 'api_call' in line and "no result" not in line:
                if apied:
                    entities = []
                    inc = False
                else:
                    apied = True
                    errs = 0
                    for elem in entities:
                        if elem not in system.split():
                            errs += 1
                            if errs >= 2:  # si dans l'appel api au moins deux entités sont manquantes: ERREUR
                                reason = "wrong api call"
                                errors += 1
                                inc = True
            
            for i in range((len(user.split()))):
                if negation(user.split()[i], ontology) and len(user.split()) > i + 1:
                    if has_word(user.split()[i + 1], ontology):  # si la négation est pas prise en compte : ERREUR
                        reason = "error negation"
                        inc = True
                        errors += 1
            
            if "bye" in user.split() or "goodbye" in user.split() or "thank" in user.split() or "thanks" in user.split():
                if "welcome" not in system.split():
                    reason = "bye system"  # si l'un ou l'autre dit au revoir mais pas l'autre ERREUR
                    inc = True
                    errors += 1
            if "welcome" in system.split():
                if not "bye" in user.split() and not "goodbye" in user.split() and not "thank" in user.split() and not "user" in system.split():
                    inc = True
                    reason = "bye user"  # si l'un ou l'autre dit au revoir mais pas l'autre ERREUR
                    errors += 1
            if apied:
                for elem in user.split():
                    if elem == "center":  # redressement moche
                        elem = 'centre'
                    
                    so, word = is_request(elem, ontology)
                    if so:
                        print("so")
                        if word not in system:  # si le systeme ne prend pas en compte la requete usr ERREUR
                            if word == 'type' or word == 'cuisine':
                                if 'food' not in system:
                                    reason = "wrong request"
                                    inc = True
                                    errors += 1
                            # if word == "address"
                if "area" in user or 'where' in user or 'part of town' in user:  # redressement moche
                    if "centre" not in system and 'north' not in system and 'south' not in system and 'east' not in system and 'west' not in system:
                        inc = True
                        reason = "not understood area"
                        errors += 1
                if ("phone" in system and "phone" not in user) or ("address" in system and "address" not in user) or (
                        "post" in system and "post" not in user):  # incomplétude ici.
                    inc = True
                    reason = "wrong guess"
        # if "eraina is a nice restaurant in the centre of town serving european food" in line:
        #     print(reason)
        #     sys.exit()
        if inc:
            if 'several' in reason:
                
                if new[-1][-2] != ')' and '<SILENCE>' not in new[-1]:
                    new[-1] = new[-1].replace('\n', '')
                    new[-1] += ' (' + reason.replace(' ', '_') + ')\n'
            else:
                # line += '(inc)'
                line += ' (' + reason.replace(' ', '_') + ')'
        line += '\n'
        print(line)
        new.append(line)
    return new, errors

def post_prod(file,out, ontology):
    out = open(out,'w')
    i = 0
    for line in file :
        if '\t' in line :
            user = line.split('\t')[0]
            system = line.split('\t')[1]
            if ('phone' in user and 'phone' not in system) or ('address' in user and 'address' not in system):
                if '(' not in line :
                    line = line.rstrip()
                    line += ' (uncomprehension)\n'
                    # sys.exit()
            if 'Sorry' in system or 'sorry' in system:
                
                for elem in user.split(' ') :
                    food = has_word(elem, ontology)
                    if food :
                        if elem not in system :
                            if '(' not in line :
                                i += 1
                                line = line.rstrip()
                                line += ' (wrong_food)\n'
                            
        out.write(line)
        
    print(i)

def open_dstc_dial(file, pack='traindev'):
    utterances = []
    errors = {}
    success = None
    polarity = 0
    for line in file['turns']:
        
        if line["transcription"] != 'noise' and line['transcription'] != 'unintelligible' and line[
            'transcription'] != 'sil':
            utterances.append(
                line['transcription'].replace(" unintelligible", "").replace("noise", "").replace('  ', " "))
    rest = file['task-information']
    for elem in rest:
        if elem == 'feedback':
            
            if rest[elem]['success'] == True:
                success = True
            else:
                success = False
            diff = 0
            words = rest[elem]['questionnaire'][0][1].split()
            
            if 'slightly' in words:
                diff = 1
            elif 'strongly' in words:
                diff = 3
            else:
                diff = 2
            if 'agree' not in words:
                polarity = (- diff) + 2
            else:
                polarity = diff + 2
            print(polarity)
    
    return utterances, polarity, success


def g_read_files(rep):
    for file in glob(rep + "**/*.json", recursive=True):
        if "label.json" in file:
            yield json.load(open(file))


def get_dials(fic, l):
    for elem in getConvs(fic):
        l.append(elem)
    return l


def rewrite(flist, dials, outnormal, outerr):
    i = 0
    err = 0
    succ = 0
    for fic in g_read_files(flist):
        i += 1
        print(i)
        ut, pol, suc = open_dstc_dial(fic)
        complete = False
        assoc = []
        for elem in ut:
            k = 0
            for dial in dials:
                k += 1
                d = Dialog(dial)
                new_d = [elem.splitted[0] for elem in d.new if
                         '\t' in elem.utterance and "<SILENCE>" not in elem.utterance]
                first = new_d[0]
                s = 0
                if "<SILENCE>" in first:
                    s += 1
                if Levenshtein.distance(elem, first) < 3:
                    j = 0
                    
                    for turn in ut[1:]:
                        j += 1
                        if len(new_d) < 2:
                            complete = False
                            break
                        if Levenshtein.distance(turn, new_d[j]) < 2:
                            complete = True
                            # sys.exit()
                        else:
                            complete = False
                            break
                
                else:
                    continue
                if complete:
                    assoc = d
                    assoc.no_change()
                    nbr = len(assoc.changed.split('\n'))
                    assoc.changed += f"{nbr} {pol}\t{suc}\n"
                    dials.remove(dial)
                    break
            if complete:
                break
        
        if not complete:
            
            err += 1
        else:
            succ += 1
            outnormal.write(assoc.changed)
            outnormal.write('\n')
    
    for dial in dials:
        d = Dialog(dial)
        d.no_change()
        nbr = len(d.changed.split('\n'))
        d.changed += f"{nbr} 0\tUNK\n"
        outerr.write(d.changed)
        outerr.write('\n')
        # if i == 12:
        #     sys.exit()
    print(err)
    print(succ)
    print(i)

    
def get_dials(file):
    dialogues = []
    dialog = []
    for line in file.readlines():
        if len(line) == 1:
            dialogues.append(dialog)
            dialog = []
        else:
            dialog.append(line.rstrip())
    return dialogues

if __name__ == '__main__':
    # i = 0
    # err = 0
    # succ = 0
    # outnormal = open('../data/dialog-bAbI-tasks/task6trndevpol.txt', 'w')
    # outerr = open("../data/dialog-bAbI-tasks/task6trndevunk.txt", 'w')
    # flist = "../data/data/"
    # # print(len(dials))
    # rewrite(flist, dials, outnormal, outerr)
    # dials = []
    # dials2 = []
    # outerr.close()
    # dials2 = get_dials(open("../data/dialog-bAbI-tasks/task6trndevunk.txt"), dials2)
    # dials2 = get_dials(open("../data/dialog-bAbI-tasks/task6tr"), dials2)
    # outnormal = open('../data/dialog-bAbI-tasks/task6testpol.txt')
    # outerr = open("../data/dialog-bAbI-tasks/task6testunk.txt")
    # outinco = open("../data/dialog-bAbI-tasks/task6testink.txt", 'w')
    fictr1 = '../data/dialog-bAbI-tasks/task6traindevinc_out.txt'
    fictr2 = '../data/dialog-bAbI-tasks/task6trndevink_out.txt'
    ficte1 = '../data/dialog-bAbI-tasks/task6testinc_out.txt'
    ficte2 = '../data/dialog-bAbI-tasks/task6testink_out.txt'
    l = [ficte1,ficte2,fictr1,fictr2]
    ontology = json.load(open("../data/dialog-bAbI-tasks/ontology.json"))
    for elem in l :
        out = elem.replace('_out.txt','_2.txt')
        elem = open(elem).readlines()
        post_prod(elem, out, ontology)

    # ontology = json.load(open("../data/dialog-bAbI-tasks/ontology.json"))
    dials = get_dials(open("../data/dialog-bAbI-tasks/task6trndevpol.txt"), dials)
    outinco = open("../data/dialog-bAbI-tasks/task6trndevinc2.txt", 'w')
    l = []
    errs = 0
    perfect = 0
    outinco.close()
    all = 0
    for elem in dials:
        old = errs
        all += 1
        n, errs = errors(elem, ontology, errs)
        outinco.write("\n" + ''.join(n))
        if old == errs:
            perfect += 1

