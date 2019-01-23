import pandas as pd
import numpy as np
import string
import re
import emoji
from time import time
from unicodedata import normalize, combining
from requests import post

class PreProcessing:
    
    def __init__(self, input_file, api_small_talks = None, id_column = None, content_column = 'Content', encoding = 'utf-8', sep = ';', batch = 4):
        data = pd.read_csv(input_file, encoding = encoding, sep = sep)
        self.data = data
        self.sep = sep
        self.encoding = encoding
        self.file_name = input_file
        self.batch = batch
        self.api_small_talks = api_small_talks
        self.abbreviations_dict = self.set_dictionary('abbreviations.txt')
        self.typo_dict = self.set_dictionary('portuguese_errors.txt')
        if type(id_column) == str: 
            self.id = data.loc[:, id_column]
        else:
            self.id = None
            
        if type(content_column) == str: 
            self.text = data.loc[:, content_column]
    
    def remove(self, message, regex_pattern, use_tagging = False, tag_name = None):
        if use_tagging == True:
            return re.sub(regex_pattern, tag_name, message)
        else:
            return re.sub(regex_pattern, ' ', message)
            
    def remove_whatsapp_emojis(self, message, use_tagging):
        if use_tagging == True:
            new_message = [word if word not in emoji.EMOJI_UNICODE.values() else 'EMOJI' for word in message]
        else:
            new_message = [word for word in message if word not in emoji.EMOJI_UNICODE.values()]
        return ''.join(new_message)
            
    def remove_emojis(self, message, use_tagging):
        emoji_pattern = re.compile('['
            u'\U0001F600-\U0001F64F'  # emoticons
            u'\U0001F300-\U0001F5FF'  # symbols & pictographs
            u'\U0001F680-\U0001F6FF'  # transport & map symbols
            u'\U0001F1E0-\U0001F1FF'  # flags (iOS)
                               ']+', flags=re.UNICODE)
        new_message = emoji_pattern.sub(r'', message)    
        return new_message
    
    def remove_spaces(self, message):
        return self.remove(message = message, regex_pattern = r'\s\s+')
    
    def remove_numbers(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'[-+]?\d*\.\d+|\d+', use_tagging = tagging, tag_name = 'NUMBER')
    
    def remove_codes(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'[A-Za-z]+\d+\w*|[\d@]+[A-Za-z]+[\w@]*', use_tagging = tagging, tag_name = 'CODE')
    
    def remove_dates(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'(\d{1,2}[/-//]\d{1,2})([/-//]\d{2,4})?', use_tagging = tagging, tag_name = 'DATE')
    
    def remove_cpf(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'\d{3}\.\d{3}\.\d{3}-\d{2}', use_tagging = tagging, tag_name = 'CPF')
        
    def remove_time(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'\d{1,2}(:|h(rs)?)(\d{1,2}(min)?)?', use_tagging = tagging, tag_name = 'TIME')
    
    def remove_emails(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'[^\s]+@[^\s]+', use_tagging = tagging, tag_name = 'EMAIL')
    
    def remove_money(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'(R[S$])\d+(\.\d{3})*(,\d{2})?', use_tagging = tagging, tag_name = 'MONEY')
        
    def remove_url(self, message, tagging):
        return self.remove(message = message, regex_pattern = r'(http|https)://[^\s]+', use_tagging = tagging, tag_name = 'URL')
    
    def remove_accentuation(self, message):
        nfkd = normalize('NFKD', message)
        word_without_accentuation = u''.join([c for c in nfkd if not combining(c)])
        return word_without_accentuation.strip()
    
    def remove_punctuation(self, message):
        pattern = '[{}]'.format(string.punctuation.replace('@',''))
        new_message = re.sub(pattern, ' ', message)
        return new_message

    def get_json(self, df):
        items_list = []
        for message in df['Processed Content']:  
            obj = {}
            obj['configuration'] = {
                'unicodeNormalization': True,
                'toLower': False,
                'informationLevel': 3
            }
            obj['text'] = message
            obj['dateCheck'] = False
            items_list.append(obj)        
        return items_list
    
    def set_dictionary(self, file_name):
        file_dict = {}
        with open(file_name,'r',encoding='utf-8') as file:
            for relation in file.read().split('\n'):
                k, v = relation.split(',')
                file_dict[k] = v
        return file_dict
                
    def use_dictionary(self, message, file_dict):    
        correct_message = []
        for word in message.split():
            if word in file_dict.keys():
                correct_message.append(file_dict[word])
            else:
                correct_message.append(word)        
        return ' '.join(correct_message)
        
    def smalltalk_requests(self, data, api_small_talks, number_of_batches, request_id):
    
        data_splitted = np.array_split(data, number_of_batches)
    
        r = []
        for idx, dataframe in enumerate(data_splitted):
            dataframe = dataframe.reset_index()
            items_list = self.get_json(dataframe)
    
            begin = time()
            obj = {'id': str(request_id) + '_' + str(idx) , 'items': items_list}
    
            r.append(post(api_small_talks, json=obj))
    
            end = time()
            print('Process finished! Time elapsed = ' + str((end - begin)) +' seconds')
        return r
    
    def converting_response_from_API(self, r, use_tagging, relevant):
        
        if use_tagging == True: cleaned_type = 'markedInput'
        elif relevant == True: cleaned_type = 'relevantInput'
        else: cleaned_type = 'cleanedInput'
        cleaned_output = []
        
        if cleaned_type != 'markedInput':
            cleaned_output = [message['analysis'][cleaned_type] if message['analysis']['matchesCount'] > 0 else '' for message in r['items']]
        else:
            for message in r['items']:   
                matches = message['analysis']['matches']
                if len(matches) > 0:
                    sorted_matches = sorted(matches, key=lambda dct: dct['index'])
                    MarkedInput = message['analysis'][cleaned_type]
                    size_diff = 0
                    st_type_lenght = 0
                    for match in sorted_matches:
                        st_lenght = match['lenght']
                        index = match['index'] + size_diff
                        
                        begin_string = MarkedInput[:index]
                        end_string = MarkedInput[index + st_lenght:]
                        MarkedInput = begin_string + match['smallTalk'].upper() + end_string
                        st_type_lenght = len(match['smallTalk'])
                        size_diff +=  st_type_lenght - st_lenght
                    cleaned_output.append(MarkedInput)
                else:
                    cleaned_output.append(message['analysis']['input'])
        return cleaned_output
    
    
    def process(self, output_file, lower = True, punctuation = True, abbreviation = True, typo = True, small_talk = True, emoji = True, wa_emoji = True, accentuation = True, number = True, relevant = False, cpf = True, url = True, email = True, money = True, code = True, time = True, date = True, tagging = True):
        
        data_processed = pd.DataFrame({'Content': self.text, 'Processed Content': self.text})
        if self.id is not None:
            data_processed.insert(0, 'Id', self.id)
        
        if emoji: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_emojis, args=(tagging,))
        if wa_emoji: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_whatsapp_emojis, args=(tagging,))
        if lower: data_processed['Processed Content'] = data_processed['Processed Content'].str.lower()
        if abbreviation: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.use_dictionary, file_dict = self.typo_dict)
        if typo: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.use_dictionary, file_dict = self.abbreviations_dict)
        if email: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_emails, args=(tagging,))
        if cpf: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_cpf, args=(tagging,))
        if money: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_money, args=(tagging,))
        if date: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_dates, args=(tagging,))
        if url: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_url, args=(tagging,))
        if time: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_time, args=(tagging,))
        if code: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_codes, args=(tagging,))
        if number: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_numbers, args=(tagging,))
        if accentuation: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_accentuation)
        if punctuation: data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_punctuation)
        data_processed['Processed Content'] = data_processed['Processed Content'].apply(self.remove_spaces)
        
        if small_talk and self.api_small_talks is not None:
            responses = self.smalltalk_requests(data_processed, self.api_small_talks, self.batch, self.data)
            processed_content = []
            for response in responses:
                without_small_talks = self.converting_response_from_API(response.json(), tagging, relevant)
                processed_content = processed_content + without_small_talks
            data_processed['Processed Content'] = processed_content
        
        data_processed.to_csv(output_file, sep= self.sep , encoding= self.encoding ,index= False)