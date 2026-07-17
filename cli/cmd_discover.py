# ==================== UDP 发现 ====================

async def cmd_discover():
    """UDP 广播发现局域网内的 Orvibo 网关。"""
    import time
    import asyncio
    import socket
    from packet import DEFAULT_KEY, ID_UNSET, PK_TYPE, build_packet, parse_packet

    async def _do_discover(timeout=3.0):
        class Proto(asyncio.DatagramProtocol):
            def __init__(self):
                self.results = []
            def datagram_received(self, data, addr):
                parsed = parse_packet(data, {ID_UNSET: DEFAULT_KEY.encode()})
                if parsed:
                    self.results.append({
                        "ip": addr[0],
                        "data": parsed,
                    })

        loop = asyncio.get_event_loop()
        payload = {
            "cmd": 86, "serial": int(str(int(time.time() * 1000))[-6:]),
            "clientType": 1, "uniSerial": int(str(int(time.time() * 1000))[-6:]),
            "serverRecord": False, "ver": "5.1.3.309",
        }
        packet = build_packet(PK_TYPE, DEFAULT_KEY.encode(), ID_UNSET, payload)

        trans, proto = await loop.create_datagram_endpoint(
            Proto, family=socket.AF_INET,
            allow_broadcast=True, local_addr=("0.0.0.0", 0),
        )
        trans.sendto(packet, ("255.255.255.255", 10000))
        await asyncio.sleep(timeout)
        trans.close()
        return proto.results

    print("\n📡 UDP 扫描网关中...\n")
    results = await _do_discover()

    if not results:
        print("❌ 未发现任何网关")
        return

    print(f"发现 {len(results)} 个网关:\n")
    for r in results:
        d = r["data"]
        print(f"  IP: {r['ip']}")
        print(f"  型号: {d.get('model', '?')}")
        print(f"  UID: {d.get('uid', '?')}")
        print(f"  MAC: {d.get('mac', '?')}")
        print()
