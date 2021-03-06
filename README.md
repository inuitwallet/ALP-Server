# ALP Server

This is the server for the ALP (Automated Liquidity Pool) system.  

[![Join the chat at https://gitter.im/inuitwallet/ALP-Server](https://img.shields.io/badge/chat-online-brightgreen.svg)](https://gitter.im/inuitwallet/ALP-Server?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
  
[![Build Status](https://travis-ci.org/inuitwallet/ALP-Server.svg?branch=master)](https://travis-ci.org/inuitwallet/ALP-Server)
[![Code Health](https://landscape.io/github/inuitwallet/ALP-Server/master/landscape.svg?style=flat)](https://landscape.io/github/inuitwallet/ALP-Server/master)
[![Heroku](https://heroku-badge.herokuapp.com/?app=alp-server&style=flat&svg=1)](https://alp-server.herokuapp.com)
  
### What is an ALP?  
Providing liquidity for the Nu network is integral to the security of the $1 peg of 
[NuBits](https://nubits.com). Liquidity ensures that consumers can always buy and sell 
NuBits at $1 on the supported exchanges. Providing this liquidity means that the liquidity 
provider (LP) is a 'Market Maker' which can leave them susceptible to and adversely 
affected 
by sharp swings in the market. The liquidity that it most at risk from this market risk
 is the funds directly supporting the peg (at just a bit more than and just a bit less 
 than $1). We call this rank 1 liquidity. The ALP model allows Nu to compensate LPs for 
 the risk of rank 1 funds and makes Liquidity provision a more attractive proposition.
   

### How does the system work?
LPs run [NuBot](https://bitbucket.org/JordanLeePeershares/nubottrading) which places 
orders on their behalf at one of the 
[exchanges](https://nubits.com/exchanges/nubits-exchanges) 
that allows NuBit trading. NuBot implements a 'parametric order book' design meaning 
that only a small percentage of the funds is used to directly support the $1 peg (rank 
1). The rest of the funds are placed in orders away from the peg which give it visible 
support but keep the funds at less risk of market movements (rank 2).  
If an ALP has been enabled in NuBot it sends some data to the ALP server every 60 
seconds. This data allows the ALP server to query the exchange API using the LPs 
exchange account and get a list of the orders that have been placed. This is done is 
such a way that the API secret key is never exposed to the ALP server so it is unable 
to carry out any other operations with the LPs exchange account.  
The ALP server looks at each placed order and decides whether they are rank 1 or rank 2
orders. Once every minute the ALP server calculates the total amount of liquidity in 
rank 1 and 2 that has been provided by all connected LPs. It then calculates the 
percentage of that total that each LP has provided. That percentage is used to reward 
the LP from a static pot of funds provided by the Nu network.  
The total reward each minute is fixed. It is decided by the ALP operators and voted 
into existence by NuShare holders using the 
[Custodial Grant](https://nubits.com/about/white-paper#custodial-grants) 
mechanism of the Nu network. The fixed reward means that LPs who provide a larger 
percentage of rank 1 liquidity will receive a higher reward but will be exposed to 
greater risk.  

---  
### ALP server details
The ALP server is inspired by the proof of concept 
[TLLP server](https://github.com/verc/nu-pool) developed by creon. It is written in 
[Python 2.7](https://www.python.org/) using the 
[Bottle](http://bottlepy.org/docs/dev/index.html) framework.  
It exposes several end points which can accept data from NuBot or any other ALP client.
These will be described below along with the details of the data they require.
All POST endpoints require the *Content-Type* header to be set to *application/json*
```
POST /register  
{  
    "user": "Exchange API public Key",  
    "address": "A valid NBT payout address",  
    "exchange": "A supported exchange",  
    "unit": "A supported currency code"  
}  
```
>Allows a client to register a new user for the exchnage/unit combination supplied. The exchange API public key serves as a user identifier.  

```
POST /liquidity
{
   "user": "The exchange API public Key used to 'register'",
   "req": "A dictionary containing the parameters required by the exchange API",
   "sign": "The result of signing req with the exchange API private key",
   "exchange": "The target exchange",
   "unit": The target currency" 
}
```
>Allows a client to submit a signed 'get_orders' request to the server. The server will use that to collect orders on behalf of the specified user and add them to the pool to be credited.  

The ALP server also exposes some endpoints that can be used for statistics collection 
or logging. These are as follows:  
```
GET /exchanges
```
>Shows an object containing the exchanges supported by this ALP and the parameters of each of them.  

```
GET /status  
```
>Shows a large data object containing lots of data about the performance of the pool and the distribution of liquidity on it. For more information and a break down of the data shown, see the Stats section.  

```
GET /<user>/orders
```
>Shows the orders on record for the given user. This includes details of any credits associated with the order.  

```
GET /<user>/stats
```
>Shows the statistics for the given user. This includes a history of the users net worth to allow for easier tracking of profit/loss.  

---
###Stats

###Requirements
libffi-dev
