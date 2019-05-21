# using python3
from segment import *
import socket
import os
import sys

class Receiver:
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = sys.argv[1]
        self.addr = (self.host, int(self.port))
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.bind(self.addr)
        self.last_received_list = []
        self.seq_from_client = 0
        self.file_size = 0
        self.copy_list = b''
        self.f = 0
        self.processing_list = []
        self.expected_seq = 0
        self.last_wrote_seq = 0
        self.last_wrote_size = 1
        self.log_file = open("Receiver_log.txt", 'w')
        self.current_checksum = 0
        self.filename_w = sys.argv[2]
        self.summary_dict = dict()
        self.summary_dict["Amount of data received (bytes)                     "] = 0
        self.summary_dict["Total Segments Received                             "] = 0
        self.summary_dict["Data segments received                              "] = 0
        self.summary_dict["Data segments with Bit Errors                       "] = 0
        self.summary_dict["Duplicate data segments received                    "] = 0
        self.summary_dict["Duplicate ACKs sent                                 "] = 0

    def three_shake_hand(self):
        while True:
            from_client_shake_1, self.addr = self.server.recvfrom(4096)
            self.last_received_list = decomposing_received_head(from_client_shake_1)
            self.summary_dict["Total Segments Received                             "] += 1
            # print(self.last_received_list)
            if self.last_received_list[4]:  # Got SYN
                print_log( 'rcv', 'S', 0, 0, 0, self.log_file )
                print('Sender wanna start connection. Approving.')
                self.file_size = self.last_received_list[7]
                shake_2 = Header(0, 1)
                shake_2.SYN = 1
                shake_2.update_head()
                self.server.sendto(shake_2.head.encode('utf-8'), self.addr)
                print_log( 'snd', 'SA', 0, 0, 1, self.log_file )
                break
        while True:
            from_client_shake_3 = self.server.recv(4096)

            self.last_received_list = decomposing_received_head(from_client_shake_3)
            self.summary_dict["Total Segments Received                             "] += 1
            # print( self.last_received_list )
            if self.last_received_list[3]: # ACK
                print_log( 'rcv', 'A', 1, 0, 1, self.log_file )
                print('Connection established!')
                return

    def getting_data(self):
        self.expected_seq = 1
        if os.path.exists(self.filename_w):
            os.remove(self.filename_w)
        self.f = open(self.filename_w, 'xb')
        while True:
            # analysis data
            datagram = self.server.recv(4096)
            self.copy_list = datagram
            self.last_received_list = decomposing_received_head(datagram)
            # print("the original datagram from client is:", self.copy_list)
            print("The header list is:", self.last_received_list)
            if self.last_received_list[5] == 1:  # FIN
                print('All data transfer successfully!')
                self.four_wave()
                return
            data_size = self.last_received_list[6]
            self.seq_from_client = self.last_received_list[0]
            actual_data = self.copy_list[-data_size:]
            # print(actual_data)
            print(f'Received {self.last_received_list[0]}--{self.last_received_list[0] + len(actual_data)}', '\n')
            self.summary_dict["Total Segments Received                             "] += 1
            self.summary_dict["Amount of data received (bytes)                     "] += data_size
            self.summary_dict["Data segments received                              "] += 1

            #checksum
            self.current_checksum = self.last_received_list[2]
            re_pack = Header(self.last_received_list[0], self.last_received_list[1])
            re_pack.data_size = data_size
            re_pack.update_head()  #checksum = 0
            if self.current_checksum != calculate_checksum(str(re_pack.head.encode("utf-8") + actual_data)):
                print_log( 'rcv/corr', 'D', self.seq_from_client, data_size, 1, self.log_file )
                print('getting bit error packages')
                self.summary_dict["Data segments with Bit Errors                       "] += 1
                continue

            # enqueue

            if self.seq_from_client < self.expected_seq: #already ack ignore
                self.summary_dict["Duplicate data segments received                    "] += 1
                print_log( 'rcv/DA', 'D', self.seq_from_client, data_size, 1, self.log_file )
                ack_datagram = Header( 1, self.expected_seq )
                ack_datagram.update_head()
                self.server.sendto( ack_datagram.head.encode( 'utf-8' ), self.addr )
                print_log( 'snd', 'A', 1, 0, self.seq_from_client, self.log_file )
                continue
            # check if its want, if so, wirte all can be wrote, send ack, update parameter
            # if not simply append
            elif self.seq_from_client == self.expected_seq: # if its wanted
                print_log( 'rcv', 'D', self.seq_from_client, data_size, 1, self.log_file )
                # add at front
                self.processing_list = [(self.seq_from_client, data_size, actual_data)] + self.processing_list
                # write
                while self.processing_list:
                    if self.last_wrote_seq + self.last_wrote_size == self.processing_list[0][0]:
                        self.f.write( self.processing_list[0][2] )
                        self.last_wrote_seq = self.processing_list[0][0]
                        self.last_wrote_size =  self.processing_list[0][1]
                        self.processing_list = self.processing_list[1:]
                    else:
                        break
                # update parameters
                self.expected_seq = self.last_wrote_seq + self.last_wrote_size
                # create head for ack and send
                ack_datagram = Header(1, self.expected_seq)
                ack_datagram.update_head()
                self.server.sendto(ack_datagram.head.encode('utf-8'), self.addr)
                print_log( 'snd', 'A', 1, 0, self.expected_seq, self.log_file )
            # if not simply append
            elif self.seq_from_client > self.expected_seq:
                print_log( 'rcv', 'D', self.seq_from_client, data_size, 1, self.log_file )
                ack_datagram = Header(1, self.expected_seq)
                ack_datagram.update_head()
                self.server.sendto(ack_datagram.head.encode( 'utf-8' ), self.addr)
                print_log( 'snd/DA', 'A', 1, data_size, self.expected_seq, self.log_file )
                self.summary_dict["Duplicate ACKs sent                                 "] += 1


                self.processing_list += [(self.seq_from_client, data_size, actual_data)]
            #sorted
            self.processing_list = sorted(self.processing_list)

    def four_wave(self):
        self.f.close()
        print_log( 'rcv', 'F', self.file_size + 1, 0, 1, self.log_file )
        self.summary_dict["Total Segments Received                             "] += 1
        print("Sender wanna close the connection. Approving.")
        wave_2 = Header(1, self.file_size + 2)  # 3030
        wave_2.update_head()
        self.server.sendto(wave_2.head.encode('utf-8'), self.addr)
        print_log( 'snd', 'A', 1, 0, self.file_size + 2, self.log_file )
        wave_3 = Header(1, self.file_size + 2)
        wave_3.FIN = 1
        wave_3.update_head()
        self.server.sendto(wave_3.head.encode('utf-8'), self.addr)
        print_log( 'snd', 'F', 1, 0, self.file_size + 2, self.log_file )
        wave_4 = self.server.recv(4096)
        self.last_received_list = decomposing_received_head(wave_4)
        self.summary_dict["Total Segments Received                             "] += 1
        # print("the wave_4 from sender is:", self.last_received_list)
        if self.last_received_list[0] == self.file_size + 2 and self.last_received_list[1] == 2:
            print_log( 'rcv', 'A', self.file_size + 2, 0, 2, self.log_file )
            print("Ok.")
            self.server.close()
            print_summary(self.summary_dict, self.log_file)
            self.log_file.close()
            os._exit(0)


R = Receiver()
R.three_shake_hand()
R.getting_data() # R.four_wave()
print('asdasdas@@#$$%%')

# R = Receiver()
# R.three_shake_hand()
# R.f = open(self.filename_w, 'xb')
# R.four_wave()