"""
只用 Python标准库的 MySQL客户端
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import socket
import struct
from decimal import Decimal

#常量

#客户端能力标志位，握手的时候要告诉服务器"我支持哪些功能"
CLIENT_LONG_PASSWORD = 0x00000001
CLIENT_LONG_FLAG = 0x00000004
CLIENT_CONNECT_WITH_DB = 0x00000008
CLIENT_PROTOCOL_41 = 0x00000200
CLIENT_TRANSACTIONS = 0x00002000
CLIENT_SECURE_CONNECTION = 0x00008000
CLIENT_MULTI_RESULTS = 0x00020000
CLIENT_PLUGIN_AUTH = 0x00080000

#命令码，发在包的第一个字节
COM_QUIT = 0x01
COM_QUERY = 0x03
COM_PING = 0x0E

#OK 状态位里的这个标记表示后面还有结果集
SERVER_MORE_RESULTS_EXISTS = 0x0008

#列的数值类型编码，用来决定取回来的值转成什么Python类型
_INT_TYPES = {0x01, 0x02, 0x03, 0x08, 0x09, 0x0D}
_DECIMAL_TYPES = {0x00, 0xF6}
_FLOAT_TYPES = {0x04, 0x05}
_BYTES_TYPES = {0xF9, 0xFA, 0xFB, 0xFC, 0xFD}


class MySQLError(Exception):
    """服务器返回的错误包，或者协议层自己发现的错误"""

    def __init__(self, message, errno=None, sqlstate=None):
        super().__init__(message)
        self.errno = errno # 服务器给的错误号
        self.sqlstate = sqlstate # 标准 SQL 状态码


#工具

def escape_string(value: str) -> str:
    """按MySQL的规则转义字符串，不含首尾的引号"""
    #反斜杠要第一个换，不然后面加进去的反斜杠会被重复转义
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\x00", "\\0")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\x1a", "\\Z")
    )


def escape(value) -> str:
    """把Python的值转成能直接拼进SQL的字面量"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        #bool要在int前面判断，因为True也是int
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value) #数字不用加引号
    if isinstance(value, (bytes, bytearray)):
        return "_binary'" + "".join("\\x%02x" % b for b in value) + "'"
    if isinstance(value, (list, tuple)):
        #列表转成SQL的 (a,b,c)，给IN用
        return "(" + ", ".join(escape(v) for v in value) + ")"
    return "'" + escape_string(str(value)) + "'"


#匹配%s占位符，预先编译一次，比每次现编译快
_PLACEHOLDER_RE = re.compile(r"%s")


def bind_params(sql: str, params) -> str:
    params = list(params)
    parts = _PLACEHOLDER_RE.split(sql)
    #切出来的段数应该比参数多一个，对不上说明调用方写错了
    if len(parts) - 1 != len(params):
        raise MySQLError(
            "参数个数与占位符不匹配：占位符 %d 个，参数 %d 个"
            % (len(parts) - 1, len(params)))
    out = []
    for index, part in enumerate(parts):
        out.append(part)
        if index < len(params):
            out.append(escape(params[index])) #段和段之间插参数
    return "".join(out)


def _read_lenenc_int(buf: bytes, pos: int):
    """读一个长度编码整数，返回 (值, 新的位置)"""
    first = buf[pos]
    if first < 0xFB:
        return first, pos + 1
    if first == 0xFB:
        return None, pos + 1 #NULL
    if first == 0xFC:
        return struct.unpack_from("<H", buf, pos + 1)[0], pos + 3
    if first == 0xFD:
        return (
            buf[pos + 1] | (buf[pos + 2] << 8) | (buf[pos + 3] << 16),
            pos + 4,
        )
    return int.from_bytes(buf[pos + 1:pos + 9], "little"), pos + 9


def _read_lenenc_str(buf: bytes, pos: int):
    """读一个长度编码字符串，先读长度再按长度取字节"""
    length, pos = _read_lenenc_int(buf, pos)
    if length is None:
        return None, pos #NULL
    return buf[pos:pos + length], pos + length


#RSA加密相关，只有全量认证那条路才会用到

class _Der:
    """很小的 DER 解析器，只用来读服务器返回的 RSA 公钥"""

    def __init__(self, data: bytes):
        self.data = data

    def read_tlv(self, pos):
        """从 pos 读一个节点，返回 (类型, 内容, 下一个节点的位置)"""
        tag = self.data[pos]
        pos += 1
        length = self.data[pos]
        pos += 1
        if length & 0x80:
            #最高位是 1，说明长度本身用了好几个字节
            n = length & 0x7F #低 7 位表示长度占几个字节
            length = int.from_bytes(self.data[pos:pos + n], "big")
            pos += n
        return tag, self.data[pos:pos + length], pos + length


def parse_rsa_public_key(pem: bytes):
    """从 PEM 格式的公钥里取出模数 n 和指数 e。

    PEM 就是一串 Base64 文本，解开之后是 DER。结构是：
        SEQUENCE
          SEQUENCE  (算法标识)
          BIT STRING
            SEQUENCE
              INTEGER  模数 n
              INTEGER  指数 e
    """
    text = pem.decode("ascii", "ignore")
    #把 -----BEGIN/END----- 那些行去掉，剩下的拼成 Base64 正文
    body = "".join(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("-----")
    )
    #补上被行尾吃掉的等号，b64decode 才会认
    der = base64.b64decode(body + "=" * (-len(body) % 4))
    d = _Der(der)
    _, spki, _ = d.read_tlv(0) #最外层的 SEQUENCE
    d2 = _Der(spki)
    _, _algorithm, pos = d2.read_tlv(0) #算法标识，不用管
    _, bitstring, _ = d2.read_tlv(pos) #BIT STRING
    #BIT STRING 的第一个字节表示有几位没用上，要去掉才是真正的 DER
    d3 = _Der(bitstring[1:])
    _, rsa_key, _ = d3.read_tlv(0) #里面这个 SEQUENCE 才是公钥
    d4 = _Der(rsa_key)
    _, n_bytes, pos = d4.read_tlv(0) #模数
    _, e_bytes, _ = d4.read_tlv(pos) #指数
    return int.from_bytes(n_bytes, "big"), int.from_bytes(e_bytes, "big")


def _mgf1(seed: bytes, length: int) -> bytes:
    """OAEP 填充用的掩码生成函数，就是把 seed 接上计数器反复哈希。"""
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha1(seed + struct.pack(">I", counter)).digest()
        counter += 1
    return out[:length]


def rsa_oaep_encrypt(message: bytes, n: int, e: int) -> bytes:
    """按 RSAES-OAEP(SHA-1) 加密，MySQL 的 sha2 认证用的就是这个方案。

    OAEP 是给明文做填充的，填完当成一个大整数做 RSA 幂运算。
    填充的作用是同样的明文每次加密结果都不同，避免被看出来。
    """
    k = (n.bit_length() + 7) // 8 #模数占几个字节，也就是密文长度
    h_len = 20 #SHA-1 的输出长度
    if len(message) > k - 2 * h_len - 2:
        raise MySQLError("待加密口令过长")
    #下面几步是 OAEP 的标准流程
    l_hash = hashlib.sha1(b"").digest() #标签为空串的哈希
    ps = b"\x00" * (k - len(message) - 2 * h_len - 2) #补零
    db = l_hash + ps + b"\x01" + message #拼成数据块
    seed = os.urandom(h_len) #随机种子，所以每次密文都不一样
    db_mask = _mgf1(seed, k - h_len - 1)
    masked_db = bytes(a ^ b for a, b in zip(db, db_mask)) #掩码后的数据块
    seed_mask = _mgf1(masked_db, h_len)
    masked_seed = bytes(a ^ b for a, b in zip(seed, seed_mask)) #掩码后的种子
    em = b"\x00" + masked_seed + masked_db #最终要加密的这块
    c = pow(int.from_bytes(em, "big"), e, n) #RSA 加密就是一次模幂运算
    return c.to_bytes(k, "big")


#连接

class MySQLConnection:
    """一条 TCP 连接上的 MySQL 会话。

    不是线程安全的：同一条连接同一时刻只能给一个线程用，
    两个线程一起收发的话包序号会乱。
    """

    def __init__(self, host="127.0.0.1", port=3306, user="root", password="",
                 database=None, charset="utf8mb4", timeout=8.0):
        self.host = host
        self.port = port
        self.user = user
        self.password = password or ""
        self.database = database
        self.timeout = timeout
        #255 是 utf8mb4，45 是 utf8 的编码，握手时要报给服务器
        self.charset_id = 255 if charset == "utf8mb4" else 45
        self._seq = 0 #当前包序号，每发一个包加一
        self._sock = None
        self._ssl = False #没走 TLS
        self.server_version = ""
        self.thread_id = 0
        self.server_capabilities = 0
        self._connect() #建好对象就直接连上

    #底层收发

    def _recv_exact(self, n: int) -> bytes:
        """一定要收满 n 个字节才返回，recv 一次可能收不全。"""
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = self._sock.recv(min(remaining, 65536))
            if not chunk:
                raise MySQLError("连接被服务器关闭")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_packet(self) -> tuple:
        """读一个完整的包。MySQL 包开头是 3 字节长度加 1 字节序号。"""
        header = self._recv_exact(4)
        #长度是小端存的
        length = header[0] | (header[1] << 8) | (header[2] << 16)
        seq = header[3]
        self._seq = (seq + 1) & 0xFF #下一个该发的序号
        if length == 0:
            return b""
        payload = self._recv_exact(length)
        #长度正好是 16MB-1 说明这个包被拆了，后面还有续包
        while length == 0xFFFFFF:
            header = self._recv_exact(4)
            length = header[0] | (header[1] << 8) | (header[2] << 16)
            self._seq = (header[3] + 1) & 0xFF
            if length:
                payload += self._recv_exact(length) #续在上一段后面
        return payload

    def _write_packet(self, payload: bytes):
        """发一个包，太长的话拆成多个。"""
        seq = self._seq
        total = len(payload)
        if total == 0:
            #空包也要发个包头
            self._sock.sendall(b"\x00\x00\x00" + bytes([seq]))
            self._seq = (seq + 1) & 0xFF
            return
        offset = 0
        while True:
            chunk = payload[offset:offset + 0xFFFFFF]
            offset += len(chunk)
            header = struct.pack("<I", len(chunk))[:3] + bytes([seq])
            self._sock.sendall(header + chunk)
            seq = (seq + 1) & 0xFF
            if len(chunk) < 0xFFFFFF:
                break #没到上限说明发完了
        self._seq = seq

    #握手认证

    def _connect(self):
        """建 TCP 连接，读握手包，把认证应答发过去。"""
        try:
            self._sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise MySQLError(
                "无法连接 MySQL %s:%s —— %s" % (self.host, self.port, exc))
        try:
            self._sock.settimeout(self.timeout)
            #关掉 Nagle，小包能立刻发出去，握手快一点
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

        self._seq = 0 #新一轮会话，序号从 0 开始
        packet = self._read_packet()
        self._parse_handshake(packet)

        #算好认证应答，连同其它信息一起发过去
        auth_response = self._scramble(
            self.server_plugin, self.server_scramble, self.password)
        self._write_packet(self._build_handshake_response(auth_response))
        self._finish_auth() #后面可能还有几轮交互

    def _parse_handshake(self, data: bytes):
        """解析服务器发来的握手包，字段是一个挨着一个排的。"""
        if not data:
            raise MySQLError("服务器没有返回握手包")
        if data[0] == 0xFF:
            self._raise_server_error(data) #直接是错误包
        self.protocol_version = data[0]
        pos = 1
        #服务器版本是个以 0 结尾的字符串
        end = data.index(b"\x00", pos)
        self.server_version = data[pos:end].decode("ascii", "replace")
        pos = end + 1
        self.thread_id = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        #随机数的前 8 个字节，用来算认证应答
        auth1 = data[pos:pos + 8]
        pos += 8
        pos += 1 #填充字节，跳过
        #能力标志的低 16 位
        cap_lower = struct.unpack_from("<H", data, pos)[0]
        pos += 2

        #下面这些字段是协议 4.1 才有的，先给个默认值
        cap_upper = 0
        charset = 33
        auth2 = b""
        plugin = "mysql_native_password"
        if len(data) > pos:
            charset = data[pos]
            pos += 1
            pos += 2 #状态标志，用不上
            cap_upper = struct.unpack_from("<H", data, pos)[0] #能力标志高 16 位
            pos += 2
            auth_len = data[pos]
            pos += 1
            pos += 10 #保留字段
            #随机数的第二部分，长度至少 13
            part2_len = max(13, auth_len - 8)
            auth2 = data[pos:pos + part2_len]
            pos += part2_len
            if len(data) > pos:
                #最后是认证插件名，也是以 0 结尾的字符串
                end = data.find(b"\x00", pos)
                if end == -1:
                    end = len(data)
                plugin = data[pos:end].decode("ascii", "replace") or plugin

        #高低位拼起来才是完整的能力标志
        self.server_capabilities = cap_lower | (cap_upper << 16)
        self.server_charset = charset
        self.server_plugin = plugin
        #两段随机数接起来，只取前 20 字节
        self.server_scramble = (auth1 + auth2)[:20]

    def _build_handshake_response(self, auth_response: bytes) -> bytes:
        """拼出客户端应答包，字段顺序是协议规定死的。"""
        capabilities = (
            CLIENT_LONG_PASSWORD
            | CLIENT_LONG_FLAG
            | CLIENT_PROTOCOL_41
            | CLIENT_TRANSACTIONS
            | CLIENT_SECURE_CONNECTION
            | CLIENT_MULTI_RESULTS
            | CLIENT_PLUGIN_AUTH
        )
        if self.database:
            capabilities |= CLIENT_CONNECT_WITH_DB #连的时候就指定库
        #只保留服务器也支持的，不然服务器会认为客户端乱来
        capabilities &= self.server_capabilities

        payload = struct.pack("<I", capabilities)
        payload += struct.pack("<I", 16 * 1024 * 1024) #最大包长
        payload += bytes([self.charset_id])
        payload += b"\x00" * 23 #保留字段，协议要求填满
        payload += self.user.encode("utf-8") + b"\x00"
        if capabilities & CLIENT_SECURE_CONNECTION:
            #长度用 1 个字节表示
            payload += bytes([len(auth_response)]) + auth_response
        else:
            payload += auth_response + b"\x00"
        if capabilities & CLIENT_CONNECT_WITH_DB:
            payload += (self.database or "").encode("utf-8") + b"\x00"
        if capabilities & CLIENT_PLUGIN_AUTH:
            payload += self.server_plugin.encode("ascii") + b"\x00"
        self._capabilities = capabilities
        return payload

    def _finish_auth(self):
        """处理认证阶段服务器可能发来的几种包。

        0x00 OK           认证通过，结束
        0xFF ERR          认证失败
        0xFE AuthSwitch   让客户端换个插件重来
        0x01 AuthMoreData 还有话说，看第二个字节
        """
        plugin = self.server_plugin
        scramble = self.server_scramble
        for _ in range(6): #最多来回 6 次，防止死循环
            packet = self._read_packet()
            if not packet:
                continue
            head = packet[0]
            if head == 0x00: #OK，认证过了
                return
            if head == 0xFF: #ERR，服务器说不行
                self._raise_server_error(packet)
            if head == 0xFE: #要换认证插件
                pos = 1
                end = packet.find(b"\x00", pos)
                if end == -1:
                    end = len(packet)
                plugin = packet[pos:end].decode("ascii", "replace")
                data = packet[end + 1:]
                scramble = data[:20] if data else scramble #新的随机数
                self.server_plugin = plugin
                self.server_scramble = scramble
                #按新插件重算一遍应答再发
                self._write_packet(self._scramble(plugin, scramble, self.password))
                continue
            if head == 0x01: #AuthMoreData
                status = packet[1]
                if plugin == "caching_sha2_password":
                    #0x03 是快速认证成功，服务器查缓存就认了，等着收 OK 就行
                    if status == 0x03:
                        continue
                    #0x04 是要做全量认证，缓存里没这条记录
                    if status == 0x04:
                        self._full_auth(plugin, scramble)
                        continue
                elif plugin == "sha256_password":
                    #这个插件直接就用这个包来要公钥
                    self._full_auth(plugin, scramble)
                    continue
                raise MySQLError("认证失败：无法识别的认证数据 0x%02x" % status)
            raise MySQLError("认证失败：无法识别的包类型 0x%02x" % head)
        raise MySQLError("认证失败：重试次数过多")

    def _full_auth(self, plugin: str, scramble: bytes):
        """缓存没命中时的全量认证。

        明文通道上不能直接把密码发出去，所以先跟服务器要它的 RSA 公钥，
        把密码加密了再发。只有走了 TLS 才可以直接发明文。
        """
        if self._ssl:
            self._write_packet(self.password.encode("utf-8") + b"\x00")
            return
        self._write_packet(b"\x02") #0x02 这个包就是"请把公钥给我"
        key_packet = self._read_packet()
        if not key_packet:
            raise MySQLError("认证失败：服务器未返回公钥")
        if key_packet[0] == 0xFF:
            self._raise_server_error(key_packet)
        if key_packet[0] == 0x01:
            key_packet = key_packet[1:] #去掉 AuthMoreData 的头
        n, e = parse_rsa_public_key(key_packet)
        payload = self._xor_password(self.password, scramble)
        self._write_packet(rsa_oaep_encrypt(payload, n, e))

    @staticmethod
    def _xor_password(password: str, scramble: bytes) -> bytes:
        """密码后面补个 0，再和随机数按位异或。"""
        raw = password.encode("utf-8") + b"\x00"
        if not scramble:
            return raw
        #随机数循环用，不够长就从头接
        return bytes(b ^ scramble[i % len(scramble)] for i, b in enumerate(raw))

    @staticmethod
    def _scramble(plugin: str, scramble: bytes, password: str) -> bytes:
        """按认证插件算出要发过去的应答。

        思路都是"拿密码和服务器给的随机数做几次哈希再异或"，
        这样密码本身不上网，而且每次连接的随机数不同，应答也不一样，
        别人截获了也没法重放。
        """
        if not password:
            return b"" #空密码直接发空
        pwd = password.encode("utf-8")
        if plugin == "mysql_clear_password":
            return pwd + b"\x00" #这个插件就是发明文，只能在加密通道上用
        if plugin == "mysql_native_password":
            stage1 = hashlib.sha1(pwd).digest()
            stage2 = hashlib.sha1(stage1).digest()
            mixed = hashlib.sha1(scramble + stage2).digest()
            return bytes(a ^ b for a, b in zip(stage1, mixed))
        if plugin in ("caching_sha2_password", "sha256_password"):
            s1 = hashlib.sha256(pwd).digest()
            s2 = hashlib.sha256(s1).digest()
            s3 = hashlib.sha256(s2 + scramble).digest()
            return bytes(a ^ b for a, b in zip(s1, s3))
        raise MySQLError("不支持的认证插件：%s" % plugin)

    def _raise_server_error(self, packet: bytes):
        """把服务器的错误包解析成异常抛出去。"""
        pos = 1
        errno = struct.unpack_from("<H", packet, pos)[0] #错误号
        pos += 2
        sqlstate = None
        #如果跟着一个 # 号，后面 5 个字节是标准 SQL 状态码
        if len(packet) > pos and packet[pos] == ord("#"):
            sqlstate = packet[pos + 1:pos + 6].decode("ascii", "replace")
            pos += 6
        message = packet[pos:].decode("utf-8", "replace") #剩下的都是错误文字
        raise MySQLError(message, errno=errno, sqlstate=sqlstate)

    #查询

    def query(self, sql: str, params=None):
        """执行一条 SQL，返回 (列名列表, 行元组列表)。

        占位符用 %s。绑定是逐个替换的，所以 SQL 里别的 % 不受影响。
        多条语句的话结果会拼在一起返回。
        """
        if params:
            sql = bind_params(sql, params)
        if self._sock is None:
            raise MySQLError("连接已关闭")
        self._seq = 0 #新命令，序号从头开始
        self._write_packet(bytes([COM_QUERY]) + sql.encode("utf-8"))

        columns = []
        rows = []
        while True:
            packet = self._read_packet()
            if not packet:
                break
            if packet[0] == 0xFF:
                self._raise_server_error(packet)
            if packet[0] == 0x00:
                #OK 包，说明这条语句没有结果集（比如 INSERT）
                status = self._ok_status(packet)
                if not status & SERVER_MORE_RESULTS_EXISTS:
                    break
                continue #后面还有结果集
            if packet[0] == 0xFB:
                raise MySQLError("不支持 LOCAL INFILE 请求")

            #结果集的结构是：列数 -> 列定义×N -> 结束包 -> 数据行×M -> 结束包
            col_count = _read_lenenc_int(packet, 0)[0]
            fields = []
            for _ in range(col_count):
                fields.append(self._read_column(self._read_packet()))
            self._read_packet() #列定义后面那个结束包，内容不用管
            columns.extend(f["name"] for f in fields)

            while True:
                row_packet = self._read_packet()
                if not row_packet:
                    break
                if row_packet[0] == 0xFF:
                    self._raise_server_error(row_packet)
                #首字节 0xFE 而且总长不到 9 字节的就是结束包。
                #数据行不可能这么短，靠这个区分
                if row_packet[0] == 0xFE and len(row_packet) < 9:
                    status = struct.unpack_from("<H", row_packet, 3)[0] \
                        if len(row_packet) >= 5 else 0
                    break
                rows.append(self._parse_row(row_packet, fields))
            if not status & SERVER_MORE_RESULTS_EXISTS:
                break
        return columns, rows

    @staticmethod
    def _ok_status(packet: bytes) -> int:
        """从 OK 包里把状态标志取出来，看后面还有没有结果集。"""
        affected, pos = _read_lenenc_int(packet, 1) #影响行数，跳过
        _last_id, pos = _read_lenenc_int(packet, pos) #自增主键，跳过
        if len(packet) > pos + 2:
            return struct.unpack_from("<H", packet, pos)[0]
        return 0

    @staticmethod
    def _read_column(packet: bytes):
        """读一个列定义包，只要列名和类型，其它字段跳过。"""
        pos = 0
        #前四个字符串是 catalog、库名、表名、原表名，用不上，跳过去
        for _ in range(4):
            _v, pos = _read_lenenc_str(packet, pos)
        name, pos = _read_lenenc_str(packet, pos) #列名
        _org_name, pos = _read_lenenc_str(packet, pos) #原始列名
        _fix_len, pos = _read_lenenc_int(packet, pos) #定长字段的长度
        _charset = struct.unpack_from("<H", packet, pos)[0] #字符集
        pos += 2
        _length = struct.unpack_from("<I", packet, pos)[0] #字段最大长度
        pos += 4
        col_type = packet[pos] #类型编码，转值的时候要用
        return {"name": name.decode("utf-8", "replace"), "type": col_type}

    @staticmethod
    def _parse_row(packet: bytes, fields):
        """按列类型把一行数据的字节转成 Python 值。"""
        values = []
        pos = 0
        for field in fields:
            raw, pos = _read_lenenc_str(packet, pos)
            if raw is None:
                values.append(None) #这一列是 NULL
                continue
            ctype = field["type"]
            text = raw.decode("utf-8", "replace")
            try:
                if ctype in _INT_TYPES:
                    values.append(int(text))
                elif ctype in _DECIMAL_TYPES:
                    values.append(Decimal(text)) #精确小数，不能用 float
                elif ctype in _FLOAT_TYPES:
                    values.append(float(text))
                elif ctype in _BYTES_TYPES:
                    values.append(text) #二进制和文本都按字符串收
                else:
                    values.append(text)
            except (ValueError, ArithmeticError):
                values.append(text) #转不动就原样返回，别把整行搞挂
        return tuple(values)

    def escape(self, value) -> str:
        return escape(value)

    def ping(self):
        """发个空命令探活，服务器能回就说明连接还通。"""
        self._seq = 0
        self._write_packet(bytes([COM_PING]))
        packet = self._read_packet()
        if packet and packet[0] == 0xFF:
            self._raise_server_error(packet)

    def close(self):
        """先礼貌地说再见，再关 socket。"""
        if self._sock is None:
            return
        try:
            self._seq = 0
            self._write_packet(bytes([COM_QUIT]))
        except OSError:
            pass #发不出去就算了，反正要关了
        try:
            self._sock.close()
        except OSError:
            pass
        self._sock = None

    def __enter__(self):
        #有了这两个方法就能写 with MySQLConnection(...) as conn
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False #返回 False 表示异常继续往外抛
