# Adapted from pyperformance; see ../vendor/pyperformance/ for source and license.

"""Script for testing the performance of json parsing and serialization.

This will dump/load several real world-representative objects a few
thousand times. The methodology below was chosen for was chosen to be similar
to real-world scenarios which operate on single objects at a time.
"""

# Python imports
import json

# Local imports


DICT = {
    'ads_flags': 0,
    'age': 18,
    'bulletin_count': 0,
    'comment_count': 0,
    'country': 'BR',
    'encrypted_id': 'G9urXXAJwjE',
    'favorite_count': 9,
    'first_name': '',
    'flags': 412317970704,
    'friend_count': 0,
    'gender': 'm',
    'gender_for_display': 'Male',
    'id': 302935349,
    'is_custom_profile_icon': 0,
    'last_name': '',
    'locale_preference': 'pt_BR',
    'member': 0,
    'tags': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    'profile_foo_id': 827119638,
    'secure_encrypted_id': 'Z_xxx2dYx3t4YAdnmfgyKw',
    'session_number': 2,
    'signup_id': '201-19225-223',
    'status': 'A',
    'theme': 1,
    'time_created': 1225237014,
    'time_updated': 1233134493,
    'unread_message_count': 0,
    'user_group': '0',
    'username': 'collinwinter',
    'play_count': 9,
    'view_count': 7,
    'zip': ''}

TUPLE = (
    [265867233, 265868503, 265252341, 265243910, 265879514,
     266219766, 266021701, 265843726, 265592821, 265246784,
     265853180, 45526486, 265463699, 265848143, 265863062,
     265392591, 265877490, 265823665, 265828884, 265753032], 60)






def bench_json_loads(objs):
    for obj in objs:
        # 20 loads
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)
        json.loads(obj)



DICT_GROUP = [{'ads_flags': '5.745254074355122e+18', 'age': '6.841777374050105e+18', 'bulletin_count': '7.334366096525491e+18', 'comment_count': '8.692569593515094e+18', 'country': '6.82435982436498e+18', 'encrypted_id': '8.506946583135982e+18', 'favorite_count': '2.675260114736814e+17', 'first_name': '4.294610970117113e+18', 'flags': '8.700929964341371e+18', 'friend_count': '5.985733746033431e+18', 'gender': '8.30934040360141e+18', 'gender_for_display': '1.0441407287869819e+18', 'id': '4.3263983386681057e+18', 'is_custom_profile_icon': '2.274232969433816e+18', 'last_name': '5.015308703812807e+18', 'locale_preference': '5.293673103535257e+18', 'member': '1.209570495402926e+17', 'tags': '1.9989795811513723e+18', 'profile_foo_id': '2.5777698394608865e+18', 'secure_encrypted_id': '8.45179427844029e+18', 'session_number': '7.06257071846422e+18', 'signup_id': '1.4720890292273613e+18', 'status': '7.352383270029485e+18', 'theme': '1.2799035264869704e+18', 'time_created': '5.694994311352681e+18', 'time_updated': '1.168594158595118e+18', 'unread_message_count': '1.6370214408128512e+16', 'user_group': '8.037290155272518e+18', 'username': '1.9318941412462285e+18', 'play_count': '1.9874629906961674e+18', 'view_count': '9.061235383560902e+18', 'zip': '8.046541388464759e+18'}, {'ads_flags': '2.668369194314582e+18', 'age': '8.868069197333565e+18', 'bulletin_count': '4.973458664398866e+18', 'comment_count': '6.25188266960104e+18', 'country': '1.888757648071681e+18', 'encrypted_id': '8.67897173578648e+18', 'favorite_count': '6.37004756708456e+18', 'first_name': '8.914982250048186e+18', 'flags': '8.243311997130569e+18', 'friend_count': '2.755841165388022e+18', 'gender': '3.33138914391184e+18', 'gender_for_display': '1.5306744566771692e+18', 'id': '1.3438629181738752e+18', 'is_custom_profile_icon': '6.008078108379474e+17', 'last_name': '2.779547103088761e+18', 'locale_preference': '5.562707885237316e+18', 'member': '3.1203768634783744e+16', 'tags': '6.252839800104303e+18', 'profile_foo_id': '3.116548464879439e+18', 'secure_encrypted_id': '2.8588573189496433e+18', 'session_number': '7.549496721360003e+18', 'signup_id': '4.434091711216032e+18', 'status': '2.9126773018956124e+18', 'theme': '4.438456207237471e+18', 'time_created': '6.499425587069929e+18', 'time_updated': '5.2574077955513446e+17', 'unread_message_count': '8.993706043853848e+18', 'user_group': '2.1089759671207834e+17', 'username': '6.915638441974233e+18', 'play_count': '7.792650769655468e+18', 'view_count': '1.6664360058521907e+17', 'zip': '7.265603445292544e+18'}, {'ads_flags': '3.3774556548101396e+18', 'age': '5.335894390717145e+18', 'bulletin_count': '8.373333913098957e+16', 'comment_count': '4.309815999706112e+17', 'country': '1.6686877460897792e+18', 'encrypted_id': '8.809979576054916e+18', 'favorite_count': '1.8125924804456673e+18', 'first_name': '6.970438093836431e+18', 'flags': '8.574556878689066e+18', 'friend_count': '8.688820713835033e+18', 'gender': '3.1763615845144996e+18', 'gender_for_display': '3.27238972639723e+18', 'id': '4.839520100667711e+18', 'is_custom_profile_icon': '7.153675157474977e+18', 'last_name': '9.966118110345103e+17', 'locale_preference': '6.902753706617102e+18', 'member': '7.353118245130537e+18', 'tags': '7.92928054383763e+18', 'profile_foo_id': '3.378666901104855e+17', 'secure_encrypted_id': '8.72346697917015e+18', 'session_number': '8.409858095261071e+17', 'signup_id': '3.142776726992565e+18', 'status': '5.633889634184356e+18', 'theme': '8.467859674442654e+18', 'time_created': '3.135573191543202e+18', 'time_updated': '8.524218479558036e+18', 'unread_message_count': '5.028066267830019e+18', 'user_group': '2.8818459995023145e+18', 'username': '2.921964129043587e+18', 'play_count': '1.636943551755901e+18', 'view_count': '7.212329416506399e+17', 'zip': '1.3730653599593196e+18'}]

objs = (json.dumps(DICT), json.dumps(TUPLE), json.dumps(DICT_GROUP))
bench_json_loads(objs)
for encoded, expected in zip(objs, (DICT, list(TUPLE), DICT_GROUP)):
    decoded = json.loads(encoded)
    assert decoded == expected
    print(len(decoded))
