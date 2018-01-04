from twisted.internet.protocol import Protocol, Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol
from twisted.internet import reactor
import json
from uuid import uuid4


SERVER_PORT = 8009

BS_HOST = "localhost"
BS_PORT = 8007
VERSION = "1.0.0"
generate_uuid = lambda: uuid4()
# 123x
def log( m, level="log"):
    delimiters = {
        "log" : "[~]",
        "error" : "[-]",
        "info" : "[+]",
        "warning" : "[!]"
    }
    print delimiters[level] , m


class MyPeerServer(LineReceiver):
    remoteNodeId = None
    remotePeer = None
    remoteHost = None
    remotePort = None
    localPeer = None
    status = 0
    peerType = None
    def __init__(self, factory=None, peerType="CLIENT"):
        log('Creating peer type ' + peerType)
        self.factory = factory
        self.peerType = peerType

    def connectionMade(self):
        log( "Connection from " + str(self.transport.getPeer()) , "info")
        self.remotePeer = self.transport.getPeer()
        self.localPeer = self.transport.getHost()

        # self.transport.write("Welcome! There are currently %d open connections.\n" %(len(self.factory.peers),))
        # self.transport.write(json.dumps({  '_v' : VERSION, 'type': 'hello', 'total_peers' : len(self.factory.peers) }))
        # self.send_handshakeRequest()

    def sendLine(self, message):            
        return self.transport.write( (message + self.delimiter) )

    def connectionLost(self, reason):
        if self.remoteNodeId in self.factory.peers:
            self.factory.peers.pop(self.remoteNodeId)
            log("Peer with nodeId " + str(self.remoteNodeId) + " has left the network. Saying Good Bye")

    def lineReceived(self, line):
        try:
            data = json.loads(line)
            {
                'req_handshake' : self.send_handshakeResponse,
                'res_handshake' : self.handle_handshake,
                'res_peers' : self.handle_peers
            }[data['type']](data)
            pass
        except ValueError as e:
            m = 'Invalid data format, expected json format'
            # print line
            log( m , "error")
            log("Disconnecting " + str(self.remotePeer), "error")
            self.transport.abortConnection()
            raise e

    def handle_handshake(self, data):
        log("Verifing handshake response from peer " + str(self.remotePeer) , "info")
        # print data
        if data['nodeId'] == self.factory.nodeId:
            log("Connected to self! OOPS!", "error")
        elif data['nodeId'] in self.factory.peers:
            log("Peer already connected")
        else:
            self.remoteNodeId = data['nodeId']
            self.remoteHost = data['host']
            self.remotePort = data['port']
            self.factory.peers[data['nodeId']] = self
            log("Peer connection with " + str(self.remotePeer) + ' is successful')
            # print self.factory.peers
        self.send_peers(self.factory.peers)

    def send_peers(self, peers):
        response = {}
        for i in peers:
            response[peers[i].remoteNodeId] = { "location" : str(peers[i].remoteHost) + ":" + str(peers[i].remotePort) , "type" : self.peerType }
        log("Sending peers to all node " + str(self.remotePeer))
        for i in peers:
            peers[i].sendLine(json.dumps({'_v' : VERSION,  'type' : 'res_peers', 'peers' :  response }))


    def handle_peers(self, data):
        log("Recieved peers from node " + str(self.remotePeer) + " - Total : " + str(len(data['peers'])))
        # print data['peers']
        for node, info in data['peers'].iteritems():
            log("Trying to connect to node - " + node )

            if(node == self.factory.nodeId):
                log("That's me in the recieved peer list - IGNORING", "warning")
                continue
            if(node in self.factory.peers):
                log("Already connected to this node - IGNORING", "warning")
                continue
            if info['type'] != "SERVER":
                log("That node is a "+ data['peers'][node]['type'] +" - IGNORING", "warning");
                continue
            location = info['location']
            host, port = location.split(":")
            point = TCP4ClientEndpoint(reactor, host, int(port))
            d = connectProtocol(point, MyPeerServer(self.factory))
            d.addCallback(gotProtocol)


    def send_handshakeRequest(self,data=None):
        log ("Requesting handshake from peer " + str(self.remotePeer) , "info")
        self.sendLine(json.dumps({ '_v' : VERSION,  'type' : 'req_handshake', 'nodeId' : self.factory.nodeId }))
    def send_handshakeResponse(self,data=None):
        log ("Recieved handshake request from peer " + str(self.remotePeer) , "info")
        self.sendLine(json.dumps({ '_v' : VERSION,  'type' : 'res_handshake', 'nodeId' : self.factory.nodeId, 'host' : self.localPeer.host, 'port' : SERVER_PORT }))        


class MyPeerFactory(Factory):
    nodeId = str(generate_uuid())
    log('Your node id is ' + nodeId)
    peers = {}
    def buildProtocol(self, addr):
        return MyPeerServer(self, "SERVER")


endpoint = TCP4ServerEndpoint(reactor, SERVER_PORT)
factory = MyPeerFactory()
endpoint.listen(factory)


def gotProtocol(p):
    p.send_handshakeResponse()

log("Bootstrapping network")
point = TCP4ClientEndpoint(reactor, BS_HOST, BS_PORT)
d = connectProtocol(point, MyPeerServer(factory))
d.addCallback(gotProtocol)
# print endpoint
reactor.run()

