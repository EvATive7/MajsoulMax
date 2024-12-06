from ruamel.yaml import YAML
from loguru import logger
from base64 import b64decode
from google.protobuf.json_format import MessageToDict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from proto import liqi_pb2 as pb
import asyncio
import uvicorn
import threading

mod_plugins = []

app = FastAPI()
wses: list[WebSocket] = {}


@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.success(f'Helper ws established')

    global wses
    wses.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.success(f'Helper ws disconnected')

        wses.remove(websocket)


def send_message(message):
    for ws in wses:
        try:
            asyncio.get_running_loop().create_task(ws.send_json(message))
        except:
            pass


class helper:
    def __init__(self):
        self.yaml = YAML()
        self.LoadSettings()
        self.method = [
            ".lq.Lobby.oauth2Login",
            ".lq.Lobby.fetchFriendList",
            ".lq.FastTest.authGame",
            ".lq.NotifyPlayerLoadGameReady",
            ".lq.ActionPrototype",
            ".lq.Lobby.fetchGameRecordList",
            ".lq.FastTest.syncGame",
            ".lq.Lobby.login"
        ]  # 需要发送给小助手的method
        self.action = [
            "ActionNewRound",
            "ActionDealTile",
            "ActionAnGangAddGang",
            "ActionChiPengGang",
            "ActionNoTile",
            "ActionHule",
            "ActionBaBei",
            "ActionLiuJu",
            "ActionUnveilTile",
            "ActionHuleXueZhanMid",
            "ActionGangResult",
            "ActionRevealTile",
            "ActionChangeTile",
            "ActionSelectGap",
            "ActionLiqi",
            "ActionDiscardTile",
            "ActionHuleXueZhanEnd",
            "ActionNewCard",
            "ActionGangResultEnd"
        ]  # '.lq.ActionPrototype'中，需要发送给小助手的action
        self.thread = threading.Thread(target=uvicorn.run, kwargs={'app': app, 'port': self.settings['config']['port']})
        self.thread.start()
        logger.success('已载入helper')

    def LoadSettings(self):
        self.settings = self.yaml.load('''\
config:
  port: 12121
''')

        try:
            with open('./config/settings.helper.yaml', 'r', encoding='utf8') as f:
                self.settings.update(self.yaml.load(f))
        except:
            logger.warning(
                '未检测到helper配置文件，已生成默认配置，如需自定义helper配置请手动修改 ./config/settings.helper.yaml')
            self.SaveSettings()

    def SaveSettings(self):
        with open('./config/settings.helper.yaml', 'w', encoding='utf8') as f:
            self.yaml.dump(self.settings, f)

    def main(self, result):
        if result['method'] in self.method:
            if result['method'] == '.lq.ActionPrototype':
                if result['data']['name'] in self.action:
                    data = result['data']['data']
                    if result['data']['name'] == 'ActionNewRound':
                        # 雀魂弃用了md5改用sha256，但没有该字段会导致小助手无法解析牌局，也不能留空
                        # 所以干脆发一个假的，反正也用不到
                        data['md5'] = data['sha256'][:32]
                else:
                    return
            elif result['method'] == '.lq.FastTest.syncGame':  # 重新进入对局时
                actions = []
                for item in result['data']['game_restore']['actions']:
                    if item['data'] == '':
                        actions.append({'name': item['name'], 'data': {}})
                    else:
                        b64 = b64decode(item['data'])
                        action_proto_obj = getattr(
                            pb, item['name']).FromString(b64)
                        action_dict_obj = MessageToDict(
                            action_proto_obj, preserving_proto_field_name=True, including_default_value_fields=True)
                        if item['name'] == 'ActionNewRound':
                            # 这里也是假md5，理由同上
                            action_dict_obj['md5'] = action_dict_obj['sha256'][:32]
                        actions.append(
                            {'name': item['name'], 'data': action_dict_obj})
                data = {'sync_game_actions': actions}
            else:
                data = result['data']
            logger.success(f'[helper] 已发送：{data}')
            send_message(data)
            if 'liqi' in data.keys():  # 补发立直消息
                logger.success(f'[helper] 已发送：{data["liqi"]}')
                send_message(data['liqi'])
