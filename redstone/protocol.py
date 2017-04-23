"""
 * Copyright (C) Redstone-Crafted (The Redstone Project) - All Rights Reserved
 * Written by Caleb Marshall <anythingtechpro@gmail.com>, April 23rd, 2017
 * Licensing information can found in 'LICENSE', which is part of this source code package.
 """

from redstone.util import DataBuffer

class PacketSerializer(object):
    ID = None
    DIRECTION = None

    def __init__(self, protocol, dispatcher):
        super(PacketSerializer, self).__init__()

        self._protocol = protocol
        self._dispatcher = dispatcher

        # each packet will reassign the data buffer to
        # its packet data buffer and will be sent via the transport buffer.
        self._dataBuffer = DataBuffer()

    @property
    def dataBuffer(self):
        return self._dataBuffer

    def serialize(self, *args, **kw):
        return False

    def serializeDone(self):
        pass

    def deserialize(self, *args, **kw):
        pass

    def deserializeDone(self):
        pass

class DisconnectPlayer(PacketSerializer):
    ID = 0x0e
    DIRECTION = 'upstream'

    def serialize(self, reason):
        self._dataBuffer.writeString(reason)

        return True

    def serializeDone(self):
        # we've just sent a disconnect message to the player,
        # but to make sure the player disconnects drop there connection.
        self._protocol.handleDisconnect()

class DespawnPlayer(PacketSerializer):
    ID = 0x0c
    DIRECTION = 'upstream'

class SpawnPlayer(PacketSerializer):
    ID = 0x07
    DIRECTION = 'upstream'

class LevelFinalize(PacketSerializer):
    ID = 0x04
    DIRECTION = 'upstream'

    def serialize(self):
        world = self._protocol.factory.world

        self._dataBuffer.writeShort(world.WORLD_WIDTH)
        self._dataBuffer.writeShort(world.WORLD_HEIGHT)
        self._dataBuffer.writeShort(world.WORLD_DEPTH)

        return True

    def serializeDone(self):
        pass

class LevelDataChunk(PacketSerializer):
    ID = 0x03
    DIRECTION = 'upstream'

    def serialize(self):
        chunkData = self._protocol.factory.world.encode()

        self._dataBuffer.writeShort(len(chunkData))
        self._dataBuffer.write(chunkData)
        self._dataBuffer.writeByte(100)

        return False

    def serializeDone(self):
        self._dispatcher.handleDispatch(LevelFinalize.DIRECTION, LevelFinalize.ID)

class LevelInitialize(PacketSerializer):
    ID = 0x02
    DIRECTION = 'upstream'

    def serializeDone(self):
        self._dispatcher.handleDispatch(LevelDataChunk.DIRECTION, LevelDataChunk.ID)

class Ping(PacketSerializer):
    ID = 0x01
    DIRECTION = 'upstream'

    def serialize(self):
        return True

class ServerIdentification(PacketSerializer):
    ID = 0x00
    DIRECTION = 'upstream'

    def serialize(self):
        self._dataBuffer.writeByte(0x07)
        self._dataBuffer.writeString('A Minecraft classic server!')
        self._dataBuffer.writeString('Welcome to the custom Mineserver!')
        self._dataBuffer.writeByte(0x64)

        return True

    def serializeDone(self):
        self._dispatcher.handleDispatch(LevelInitialize.DIRECTION, LevelInitialize.ID)

class PlayerIdentification(PacketSerializer):
    ID = 0x00
    DIRECTION = 'downstream'

    def deserialize(self, dataBuffer):
        try:
            protocolVersion = dataBuffer.readByte()
            username = dataBuffer.readString()
        except:
            self._protocol.closeConnection()
            return

        self._dispatcher.handleDispatch(ServerIdentification.DIRECTION, ServerIdentification.ID)

class PacketDispatcher(object):

    def __init__(self, protocol):
        super(PacketDispatcher, self).__init__()

        self._protocol = protocol
        self._packets = {
            'downstream': {
                PlayerIdentification.ID: PlayerIdentification,
            },
            'upstream': {
                ServerIdentification.ID: ServerIdentification,
                Ping.ID: Ping,
                LevelInitialize.ID: LevelInitialize,
                LevelDataChunk.ID: LevelDataChunk,
                LevelFinalize.ID: LevelFinalize,
                SpawnPlayer.ID: SpawnPlayer,
                DespawnPlayer.ID: DespawnPlayer,
                DisconnectPlayer.ID: DisconnectPlayer,
            }
        }

    def handleDispatch(self, direction, packetId, *args, **kw):
        if direction not in self._packets:
            self.handleDiscard(packetId)
            return

        if packetId not in self._packets[direction]:
            self.handleDiscard(packetId)
            return

        packet = self._packets[direction][packetId](self._protocol, self)

        if direction != packet.DIRECTION:
            return

        # handle the packet by the direction in which the data
        # is traveling, upsteam or downsteam.
        self.handlePacket(packet, packet.DIRECTION, *args, **kw)

    def handlePacket(self, packet, direction, *args, **kw):
        if direction == 'downstream':
            packet.deserialize(*args, **kw)
        elif direction == 'upstream':
            canSendData = packet.serialize(*args, **kw)

            dataBuffer = DataBuffer()
            dataBuffer.writeByte(packet.ID)
            dataBuffer.write(packet.dataBuffer.data)

            self._protocol.transportBuffer.add(dataBuffer.data)

            if canSendData:
                self._protocol.transportBuffer.send()

            # the data has been sent, now give the packer handler
            # a change to send any following data.
            packet.serializeDone()

    def handleDiscard(self, packetId):
        pass
