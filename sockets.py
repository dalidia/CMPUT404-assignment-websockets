#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Copyright (c) 2022 Lidia Ataupillco Ramos
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from flask import Flask, request, redirect, jsonify, Response
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

clients = list()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()        

class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

# TODO: I think there's an issue with the set_listener
def set_listener( entity, data ):
    ''' do something with the update ! '''
    myWorld.set( entity, data )
    print("I CAME HERE")

myWorld.add_set_listener( set_listener )

@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect('/static/index.html', code=302)

def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # XXX: TODO IMPLEMENT ME
    try:
        while True:
            msg = ws.receive()
            print("WS RECV: %s", msg)
            print("WS TYPE: %s", type(msg))

            if msg is not None:
                packet_obj = json.loads(msg)
                # myWorld.update_listeners(packet_obj)
                # # TODO: change this
                for client_temp in clients:
                    client_temp.put(packet_obj)

                print("PACKET", packet_obj)
            else:
                break
    except Exception as e:
        print("WS Error %s" % e)

    return None

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
        websocket and read updates from the websocket '''
    # initializing the clients
    client = Client()
    clients.append(client)

    # read from the websocket
    g = gevent.spawn( read_ws, ws, client)
    print("DO I GO HERE?")

    try:
        while True:
            # TODO: change this to give the world state
            data = client.get()
            print("I am here")
            ws.send(json.dumps({"data":data}))
    except Exception as e:
        print("WS Error %s" % e)
    finally:
        clients.remove(client)
        gevent.kill(g)

    return None


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
        that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    try:
        data = flask_post_json()
        if request.method == 'POST':
            myWorld.set(entity, data)
        elif request.method == 'PUT':
            for key in data:
                myWorld.update(entity, key, data[key])

        return jsonify(myWorld.get(entity))

    except Exception as e:
        print("update failed: %s" % e)
        return Response(status=500, response=json.dumps({'Error': str(e)}))

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    return jsonify(myWorld.world())

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    try:
        rep_entity = myWorld.get(entity)
        return jsonify(rep_entity)
    except Exception as e:
        return Response(status=500, response=json.dumps({'Error': str(e)}))

@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    if request.method == 'POST':
        myWorld.clear()
        return jsonify(myWorld.world())
    
    return jsonify(myWorld.world())

if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
