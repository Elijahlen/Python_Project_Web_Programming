# using python3
from segment import *
import socket
import sys
import time
import os
import random

class Sender:
    def __init__(self):
        self.MWS = int(sys.argv[4])
        self.MSS = int(sys.argv[5])
        self.w_number = self.MWS // self.MSS
        self.window = []
        self.package = 0
        self.data_list = []
        self.file_name = sys.argv[3]
        self.host = sys.argv[1]
        self.port = sys.argv[2]
        self.addr = (self.host, int(self.port))
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.file_size = 0
        self.last_received_ack = 0
        self.received_list = []
        self.send_visited_list = []
        self.dup_Acc = 0
        self.index_tobe_inwindow = 0
        self.log_file = open("Sender_log.txt", "w")
        self.reorder_package = 0
        self.reorder_Acc = -1
        self.last_du_flag = 0

        self.summary_dict = dict()
        self.summary_dict["Size of the file (in Bytes)                         "] = 0
        self.summary_dict["Segments transmitted (including drop & RXT)         "] = 0
        self.summary_dict["Number of Segments handled by PLD                   "] = 0
        self.summary_dict["Number of Segments dropped                          "] = 0
        self.summary_dict["Number of Segments Corrupted                        "] = 0
        self.summary_dict["Number of Segments Re-ordered                       "] = 0
        self.summary_dict["Number of Segments Duplicated                       "] = 0
        self.summary_dict["Number of Segments Delayed                          "] = 0
        self.summary_dict["Number of Retransmissions due to TIMEOUT            "] = 0
        self.summary_dict["Number of FAST RETRANSMISSION                       "] = 0
        self.summary_dict["Number of DUP ACKS received                         "] = 0

        self.gamma = int(sys.argv[6])
        self.initial_eRTT = 500
        self.initial_DevRTT = 250
        self.eRTT =  self.initial_eRTT
        self.DevRTT = self.initial_DevRTT
        self.Sample_RTT = 0
        self.interval = self.initial_eRTT + 4 * self.initial_DevRTT  # 1500

        self.pDrop = float(sys.argv[7])
        self.pDuplicate = float(sys.argv[8])
        self.pCorrupt = float(sys.argv[9])
        self.pOrder = float(sys.argv[10])
        self.pDelay = float(sys.argv[12])
        self.maxorder = int(sys.argv[11])
        self.maxDelay = int(sys.argv[13])
        self.seed = int(sys.argv[14])
        random.seed(self.seed)

    def read_file(self):
        f = open(self.file_name,'rb')
        cont = f.read(self.MSS)
        while len(cont) > 0:
            self.data_list = self.data_list + [cont]
            # print(cont, "length is:", len(cont))
            cont = f.read(self.MSS)
        f.close()
        self.file_size = os.path.getsize(self.file_name)
        self.summary_dict["Size of the file (in Bytes)                         "] = self.file_size
        self.package = len(self.data_list)
        self.send_visited_list = [0] * self.package

    def three_shake_hand(self):
        print('Trying to establish the connection with server.')
        shake_1 = Header()
        shake_1.SYN = 1
        shake_1.file_size = self.file_size
        shake_1.update_head()
        self.client.sendto(shake_1.head.encode('utf-8'), self.addr)
        print_log( 'snd', 'S', 0, 0, 0, self.log_file )
        self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
        from_server_byte_shake_2 = self.client.recv(4096)
        self.received_list = decomposing_received_head(from_server_byte_shake_2)
        self.last_received_ack = self.received_list[1]  # ack = 1
        if self.received_list[4] and self.received_list[3]:  # SYN and ACK
            print_log( 'rcv', 'SA', 0, 0, 1, self.log_file )
            print('Got approval from server.')
            shake_3 = Header(1, 1)
            shake_3.update_head()
            self.client.sendto(shake_3.head.encode('utf-8'), self.addr)
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            print_log( 'snd', 'A', 1, 0, 1, self.log_file )
            print( 'Start transfering file.' )
            return


    def four_wave(self):

        sqe_number = self.file_size + 1  #3029
        wave_1 = Header(sqe_number, 1)
        wave_1.FIN = 1
        wave_1.update_head()
        self.client.sendto(wave_1.head.encode('utf-8'), self.addr)
        self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
        print_log( 'snd', 'F', sqe_number, 0, 1, self.log_file )# send first tear down
        # time.sleep(1)
        while True:
            try:
                from_server_byte_wave_2 = self.client.recv(4096)
                print('Got it closing approval.')
                break
            except BlockingIOError:
                pass
        self.received_list = decomposing_received_head(from_server_byte_wave_2)
        if self.received_list[1] == sqe_number + 1:
            print("Sender is already closed.")
            print_log( 'rcv', 'A', 1, 0, self.received_list[1], self.log_file )
            # time.sleep(1)
            while True:
                try:
                    from_server_byte_wave_3 = self.client.recv( 4096 )
                    print( 'Got it' )
                    break
                except BlockingIOError:
                    pass
            self.received_list = decomposing_received_head(from_server_byte_wave_3)
            if self.received_list[5] and self.received_list[0]:
                print("Server wanna close the connection, approving")
                print_log( 'rcv', 'F', 1, 0, self.received_list[1], self.log_file )
                wave_4 = Header(self.received_list[1], self.received_list[0] + 1)
                wave_4.update_head()
                self.client.sendto(wave_4.head.encode('utf-8'), self.addr)  # send last tear down
                print_log( 'snd', 'A', self.received_list[1], 0, 2, self.log_file )
                self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
                self.client.close()
                print_summary(self.summary_dict, self.log_file)
                self.log_file.close()
                print('Ok')
                os._exit(0)
            else:
                print( 'Somthing is really wrong 2.' )
                os._exit( 0 )
        else:

            print('Somthing is really wrong 1.')
            print('Please check this:',self.received_list)
            os._exit( 0 )

        # except BlockingIOError:
        #     pass

    def update_interval(self, RTT):
        self.DevRTT = 0.75 * self.DevRTT + 0.25 * abs(RTT - self.eRTT)
        self.eRTT = 0.875 * self.eRTT + 0.125 * RTT
        self.interval = self.eRTT + self.gamma * self.DevRTT

    def check_timeout(self):
        for p in self.window:   # [w_segment1,w_segment2, ...]
            if p:
                if (time.time() - p.send_time) * 1000 > p.interval:
                    self.client.sendto(p.datagram,self.addr)
                    print( 'Restransfering :', p.datagram )
                    num = random.random()
                    p.send_time = time.time()
                    print_log( 'snd/RXT', 'D', p.seq, p.data_length, 1, self.log_file )
                    self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
                    self.summary_dict["Number of Retransmissions due to TIMEOUT            "] += 1
                    self.summary_dict["Number of Segments handled by PLD                   "] += 1
                    self.check_and_send_reorder()

    def try_receive_ACK(self):
        self.client.settimeout(0)
        try:
            ack_datagram = self.client.recv(4096) # self.last_received_ack = 1
            self.received_list = decomposing_received_head(ack_datagram)
            print('Received ACK list from server:', self.received_list)
            print(f'The data before {self.received_list[1]} already transfer successfully!\n')
            if self.received_list[1] == self.last_received_ack:  # same as w[0] seq
                print_log( 'rcv/DA', 'A', 1, 0, self.last_received_ack, self.log_file )
                self.summary_dict["Number of DUP ACKS received                         "] += 1
                self.dup_Acc += 1
                if self.dup_Acc == 3:
                    self.dup_Acc = 0
                    for p in self.window:
                        if p.seq == self.received_list[1]:
                            self.client.sendto(p.datagram, self.addr)  ########for now
                            num = random.random()
                            p.send_time = time.time()
                            print_log( 'snd/RXT', 'D', p.seq, p.data_length, 1, self.log_file )
                            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
                            self.summary_dict["Number of FAST RETRANSMISSION                       "] += 1
                            self.summary_dict["Number of Segments handled by PLD                   "] += 1
                            self.check_and_send_reorder()

            else: # new ack should be same as w[1:] the right case must not empty
                # finding the index of matched segment update_interval
                self.last_received_ack = self.received_list[1]
                print_log( 'rcv', 'A', 1, 0, self.last_received_ack, self.log_file )
                current_time = time.time()
                for p in self.window:
                    if p.seq + p.data_length == self.received_list[1]:
                        self.Sample_RTT = current_time - p.send_time
                        self.update_interval(self.Sample_RTT * 1000)
                        break
                self.dup_Acc = 0


        except BlockingIOError:
            pass

    def slide_window(self):
        # dequeque
        while self.window: #and not(self.window[0] is None):  # self.window is not empty
            if self.window[0].seq + self.window[0].data_length <= self.last_received_ack:
                self.window.remove( self.window[0] )
            else:
                break
        # enqueque
        if self.index_tobe_inwindow <= self.package - 1:
            if len(self.window) < self.w_number:
                difference = self.w_number - len( self.window )
                self.window = self.window + [None] * difference   # make up

                for i in range(len(self.window)):   #should be same as self.w_number
                    if not self.window[i]:  # loading
                        self.window[i] = w_segment(self.index_tobe_inwindow, self.interval)
                        self.window[i].seq = 1 + self.index_tobe_inwindow * self.MSS
                        # loading the Header of datagram of w_segment
                        new_datagram = Header(self.window[i].seq, 1)
                        new_datagram.data_size = len(self.data_list[self.index_tobe_inwindow])
                        new_datagram.update_head()
                        tobe_checksum = new_datagram.head.encode('utf-8') + self.data_list[self.index_tobe_inwindow]
                        new_datagram.checksum = calculate_checksum(str(tobe_checksum))  #loading check_sum
                        new_datagram.update_head()
                        self.window[i].datagram = new_datagram.head.encode('utf-8') + self.data_list[self.index_tobe_inwindow]
                        self.window[i].data_length = len(self.data_list[self.index_tobe_inwindow])
                        # send_time to be update
                        self.index_tobe_inwindow += 1
                         # self.index_tobe_inwindow = self.package - 1  last one already in

    def check_window_sending(self):

        for p in self.window:
            if p:
                if not self.send_visited_list[p.index]: # not ever sent yet
                    self.PLD_sent(p)
                    self.send_visited_list[p.index] = 1

    def PLD_roller(self):
        #           0: safe_package
        #           1: pDrop
        #           2: pDuplicate
        #           3: pCorrupt
        #           4: pOrder
        #           5: pDelay
        num = random.random()
        if num < self.pDrop:
            return 1

        num = random.random()
        if num < self.pDuplicate:
            return 2

        num = random.random()
        if num < self.pCorrupt:
            return 3

        num = random.random()
        if num < self.pOrder:
            return 4

        num = random.random()
        if num < self.pDelay:
            return 5

        return 0

    def check_and_send_reorder(self):
        if self.reorder_package == 0:  # then self.reorder_Acc must be -1 not need send reorder
            return
        self.reorder_Acc -= 1
        if self.reorder_Acc == 0:
            self.client.sendto( self.reorder_package.datagram, self.addr )
            print_log( 'snd/rord', 'D', self.reorder_package.seq, self.reorder_package.data_length, 1, self.log_file )
            self.reorder_package.send_time = time.time()
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            self.reorder_package = 0
            self.reorder_Acc = -1

    def PLD_sent(self, p):
        self.summary_dict["Number of Segments handled by PLD                   "] += 1
        flag_number = self.PLD_roller()
        if flag_number == 0:    # safe
            self.client.sendto( p.datagram, self.addr )
            p.send_time = time.time()
            print_log('snd', 'D', p.seq, p.data_length, 1, self.log_file )
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            self.check_and_send_reorder()
            return

        elif flag_number == 1:   # drop
            p.send_time = time.time()
            print_log( 'drop', 'D', p.seq, p.data_length, 1, self.log_file )
            print(f'{p.seq}--{p.seq + p.data_length} dropped.')
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            self.summary_dict["Number of Segments dropped                          "] += 1
            self.check_and_send_reorder()
            return

        elif flag_number == 2:   # duplicated
            if p.seq == self.file_size + 1:
                self.last_du_flag = 1
            self.summary_dict["Number of Segments Duplicated                       "] += 1
            self.client.sendto( p.datagram, self.addr )
            print_log( 'snd', 'D', p.seq, p.data_length, 1, self.log_file )
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            self.check_and_send_reorder()
            self.client.sendto( p.datagram, self.addr )
            print_log( 'snd/dup', 'D', p.seq, p.data_length, 1, self.log_file )
            print( f'{p.seq}--{p.seq + p.data_length} duplicated.' )
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            self.check_and_send_reorder()
            p.send_time = time.time()
            return

        elif flag_number == 3:   # corrupt
            corrput_data = p.datagram
            corrput_data = corrput_data[:-1]
            corrput_data = corrput_data + b'~'
            self.client.sendto( corrput_data, self.addr )
            print('Sending corrupts :', corrput_data)
            print_log( 'snd/corr', 'D', p.seq, p.data_length, 1, self.log_file )
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            self.summary_dict["Number of Segments Corrupted                        "] += 1
            p.send_time = time.time()
            self.check_and_send_reorder()
            return

        elif flag_number == 4:   # reorder
            if self.reorder_package:
                self.client.sendto( p.datagram, self.addr )
                p.send_time = time.time()
                print_log( 'snd', 'D', p.seq, p.data_length, 1, self.log_file )
                self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
                self.check_and_send_reorder()
                return
            else:
                print( f'{p.seq}--{p.seq + p.data_length} reordered.' )
                self.reorder_package = p
                self.reorder_Acc = self.maxorder
                self.summary_dict["Number of Segments Re-ordered                       "] += 1

        elif flag_number == 5:   # delay
            self.summary_dict["Number of Segments Delayed                          "] += 1
            print( f'{p.seq}--{p.seq + p.data_length} delayed.' )
            time.sleep(self.maxDelay/1000)
            self.client.sendto( p.datagram, self.addr )
            p.send_time = time.time()
            print_log( 'snd/dely', 'D', p.seq, p.data_length, 1, self.log_file )
            self.summary_dict["Segments transmitted (including drop & RXT)         "] += 1
            self.check_and_send_reorder()
            return



class w_segment:
    def __init__(self, index, interval):  # time = time.time()
        self.index = index  # interval = self.interval
        self.seq = 0 # to be update after create
        self.datagram = b''  # to be update after create
        self.data_length = 0 # to be update after create
        self.send_time = 0  # when send in widow
        self.interval = interval



S = Sender()

S.read_file()
S.three_shake_hand()
while True:
    S.check_timeout()
    S.try_receive_ACK()  # # S.four_wave()
    S.slide_window()
    S.check_window_sending()
    if S.last_received_ack == S.file_size + 1:
        time.sleep( 5 )
        # cleaning received buff:self.client.recv( 4096 )
        while True:
            S.client.settimeout(0)

            try:
                clean = S.client.recv(4096)
                clean = 0
            except BlockingIOError:
                pass
                S.four_wave()











