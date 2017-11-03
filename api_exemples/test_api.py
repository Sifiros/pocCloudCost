#!/usr/bin/env python3

import requests

def main():
    try:

        # Classic requests with HTPP verbs
        r = requests.get('https://api.github.com/events')
        print(r.text)
        print(r.json())

        #r = requests.post('http://httpbin.org/post', data = {'key':'value'})
        #r = requests.put('http://httpbin.org/put', data = {'key':'value'})
        #r = requests.delete('http://httpbin.org/delete')
        #r = requests.head('http://httpbin.org/get')

        # Requests with URL parameters

        payload = {'key1': 'value1', 'key2': 'value2'}
        r = requests.get('http://httpbin.org/get', params=payload)
        print('URL encoded => ' + r.url)

        # all None are obviously not sent

        # list by URL

        payload = {'key1': 'value1', 'key2': ['value2', 'value3']}
        r = requests.get('http://httpbin.org/get', params=payload)
        print(r.url)

        # to check if a request succeed

        r.raise_for_status()
        # or use
        print(r.status_code)
        r.status_code == requests.codes.ok

        # to write big things in a file

#        with open('MonSuperFileName', 'wb') as fd:
#            for chunk in r.iter_content(chunk_size=128):
#                fd.write(chunk)

        # Header customisaton

        url = 'https://api.github.com/some/endpoint'
        headers = {'user-agent': 'my-app/0.0.1'}
        r = requests.get(url, headers=headers)


        # adding timout

        requests.get('http://github.com', timeout=0.001)


    except Exception as e:
        print('Error cuz => ' + e)
        exit(1)


if __name__ == '__main__':
    main()
