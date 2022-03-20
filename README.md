# sopel-wolframalpha
Sopel IRC bot plugin to query Wolfram Alpha.
Ported from [oddluck/limnoria-plugins](https://github.com/oddluck/limnoria-plugins/tree/master/WolframAlpha).

### Setup

```bash
cd "~/.sopel/plugins/"
wget https://raw.githubusercontent.com/dowodenum/sopel-wolframalpha/main/wolframalpha.py
pip3 install requests
pip3 install xml
```

### Configuration

Add the following block in your sopel config file (~/.sopel/default.cfg by default):
```
[wolfram]
apiKey = D34DB33FF33D
maxOutput = 3
```
- `apiKey`:
  - Your Wolfram Alpha API key. Get one: http://api.wolframalpha.com/

- `maxOutput`:
  - Integer. Maxmimum number of result lines to be printed at once. Suggested default of 3.

### Usage

From the IRC channel you configured in the last step (adjust from `.` to your bot's configured prefix)...
The first line must be performed by a bot admin (you):
```
<you> /msg bot .load wolframalpha
<you> .wa next full moon
<bot> Input interpretation :: next full moon
<bot> Result :: Saturday, April 16, 2022
<bot> Full moon name :: pink moon
```
