###
# Copyright (c) 2014, spline
# Copyright (c) 2020, oddluck <oddluck@riseup.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

###
# Ported to Sopel by SirVo, 2022
###


# my libs
from collections import defaultdict

try:
    import xml.etree.cElementTree as ElementTree
except ImportError:
    import xml.etree.ElementTree as ElementTree

from sopel.module import commands, example
from sopel.plugin import search
from sopel import formatting, tools
from sopel.config.types import StaticSection, ValidatedAttribute
import re, requests

# optionally define a 'bridge' bot username to listen for,
# interpreting commands from the user at the other end of the bridge
# see "reWa" function - manual config of command prefix is required
# for the plugin.search regex.
bridgeBot = ""

class WolframAlphaSection(StaticSection):
    apiKey = ValidatedAttribute('apiKey', default=None)
    maxOutput = ValidatedAttribute('maxOutput', default=None)

def configure(config):
    config.define_section('wolfram', WolframAlphaSection, validate=False)
    config.wolfram.configure_setting('apiKey', 'wolframalpha.com API key')
    config.wolfram.configure_setting('maxOutput', 'Maximum lines to print at once.')

def setup(bot):
    bot.config.define_section('wolfram', WolframAlphaSection)

######################
# INTERNAL FUNCTIONS #
######################

def _red(s):
    return formatting.color(s, fg="RED")

def _bold(s):
    return formatting.bold(s)

####################
# PUBLIC FUNCTIONS #
####################

# API Documentation. http://products.wolframalpha.com/api/documentation.html
def wolframalpha(bot, query, nick):
    """[--num #|--reinterpret|--usemetric|--shortest|--fulloutput] <query>

    Returns answer from Wolfram Alpha API.

    Use --num number to display a specific amount of lines.
    Use --reinterpret to have WA logic to interpret question if not understood.
    Use --usemetric to not display in imperial units.
    Use --shortest for the shortest output (ignores lines).
    Use --fulloutput to display everything from the API (can flood).
    """
    apiKey = bot.config.wolfram.apiKey
    maxOutput = int(bot.config.wolfram.maxOutput)

    # check for API key before we can do anything.
    if not apiKey:
        bot.say(nick + ': Wolfram Alpha API key not set. Contact your bot herder.')
        return
    # first, url arguments, some of which getopts and config variables can manipulate.
    urlArgs = {
        "input": query,
        "appid": apiKey,
        "reinterpret": "true",
        "format": "plaintext",
        "units": "nonmetric"
    }
    # now handle input. default input arguments.
    args = {
        "maxoutput": maxOutput,
        "shortest": None,
        "fulloutput": None,
    }
    
    # build url and query.
    url = "http://api.wolframalpha.com/v2/query"
    try:
        page = requests.get(url, params=urlArgs)
    except Exception as e:
        print("ERROR opening {0} message: {1}".format(url, e))
        bot.say(nick + ": ERROR: Failed to open WolframAlpha API: {0}".format(url))
        bot.say(e)
        return
    # now try to process XML.
    try:
        document = ElementTree.fromstring(page.text)
    except Exception as e:
        print("ERROR: Broke processing XML: {0}".format(e))
        bot.say(nick + ": ERROR: Something broke processing XML from WolframAlpha's API.")
        return
    # document = ElementTree.fromstring(page) #.decode('utf-8'))
    # check if we have an error. reports to irc but more detailed in the logs.
    if document.attrib["success"] == "false" and document.attrib["error"] == "true":
        errormsgs = []
        for error in document.findall(".//error"):
            errorcode = error.find("code").text
            errormsg = error.find("msg").text
            errormsgs.append("{0} - {1}".format(errorcode, errormsg))
        # log and report to irc if we have these.
        print(
            "ERROR processing request for: {0} message: {1}".format(
                errormsgs
            )
        )
        bot.say(nick + ': '
            "ERROR: Something went wrong processing request for: {0} ERROR: {1}"
            .format(optinput, errormsgs)
        )
        return
    # check if we have no success but also no error. (Did you mean?)
    elif (
        document.attrib["success"] == "false"
        and document.attrib["error"] == "false"
    ):
        errormsgs = []  # list to contain whatever is there.
        for error in document.findall(".//futuretopic"):
            errormsg = error.attrib["msg"]
            errormsgs.append("FUTURE TOPIC: {0}".format(errormsg))
        for error in document.findall(".//didyoumeans"):
            errormsg = error.find("didyoumean").text
            errormsgs.append("Did you mean? {0}".format(errormsg))
        for error in document.findall(".//tips"):
            errormsg = error.find("tip").attrib["text"].text
            errormsgs.append("TIPS: {0}".format(errormsg))
        # now output the messages to irc and log.
        print(
            "ERROR with input: {0} API returned: {1}".format(optinput, errormsgs)
        )
        bot.say(nick + ': '
            "ERROR with input: {0} API returned: {1}".format(optinput, errormsgs)
        )
        return
    else:  # this means we have success and no error messages.
        # each pod has a title, position and a number of subtexts. output contains the plaintext.
        # outputlist is used in sorting since defaultdict does not remember order/position.
        output = defaultdict(list)
        outputlist = {}
        # each answer has a different amount of pods.
        for pod in document.findall(".//pod"):
            title = pod.attrib["title"]  # title of it.
            position = int(pod.attrib["position"])  # store pods int when we sort.
            outputlist[position] = title  # pu
            for plaintext in pod.findall(".//plaintext"):
                if plaintext.text:
                    output[title].append(plaintext.text.replace("\n", " "))
    # last sanity check...
    if len(output) == 0:
        bot.say(nick + ": ERROR: I received no output looking up: {0}".format(optinput))
        return
    # done processing the XML so lets work on the output.
    # the way we output is based on args above, controlled by getopts.
    else:  # regular output, dictated by --lines or maxoutput.
        for q, k in enumerate(sorted(outputlist.keys())):
            if q < maxOutput:  # if less than max.
                itemout = output.get(
                    outputlist[k]
                )  # have the key, get the value, use for output.
                if itemout:
                    bot.say(
                        re.sub(
                            "\s+",
                            " ",
                            "{0} :: {1}".format(
                                _red(outputlist[k]), " | ".join(itemout)
                            ),
                        ).replace(": | ", ": ")
                    )

@commands('wa', 'wolfram', 'wolframalpha')
@example('.wa next full moon')
def wa(bot, trigger):
    wolframalpha(bot, trigger.group(2), trigger.nick)

@search('\.(wa|wolfram|wolframalpha)\s(.*)?')
def reWa(bot, trigger):
    if not trigger.nick == bridgeBot:
        return
    else:
        reg = re.search(r'(.*): \.(wa|wolfram|wolframalpha)\s(.*)?', trigger)
        nick = reg.group(1)
        query = reg.group(3)

    wolframalpha(bot, query, nick)
