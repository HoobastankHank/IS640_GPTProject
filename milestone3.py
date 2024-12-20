import torch
import torch.nn as nn
from torch.nn import functional as Func

# seed generation
torch.manual_seed(1337)

#MODEL PARAMETERS
batch_size = 4 # how many independent sequences will we process in parallel?
block_size = 8 # what is the maximum context length for predictions?
max_iters = 1000
eval_interval = 100
learning_rate = 1e-3
device = 'cuda' if torch.cuda.is_available() else 'cpu'
eval_iters = 200
n_embd = 64
n_head = 4
n_layer = 4
dropout = 0.0
# --------------------------------------------------------------


#MILESTONE 1
#open the file text
with open('data/bible.txt', 'r', encoding='utf-8') as script:
    read = script.read()

#all the characters to be encoded
char = sorted(list(set(read)))
vocab = len(char)

# ENCODE and DECODE
stoi = { ch:i for i,ch in enumerate(char) }
itos = { i:ch for i,ch in enumerate(char) }
encode = lambda s: [stoi[c] for c in s] # encoder: take a string, output a list of integers
decode = lambda l: ''.join([itos[i] for i in l]) # decoder: take a list of integers, output a string

# Training and Testing
num_data = torch.tensor(encode(read), dtype=torch.long)
n = int(0.9*len(num_data)) # first 90% will be train, rest val
train_half = num_data[:n]
val_half = num_data[n:]

# data loading
def get_batch(split):
    # generate a small batch of data of inputs x and targets y
    data = train_half if split == 'train' else val_half
    ix = torch.randint(len(data) - block_size, (batch_size,))
    x = torch.stack([data[i:i+block_size] for i in ix])
    y = torch.stack([data[i+1:i+block_size+1] for i in ix])
    x, y = x.to(device), y.to(device)
    return x, y
#-------------------------------------------------------------

#MILESTONE2
@torch.no_grad()
def estimate_loss():
    out = {}
    model.eval()
    for split in ['train', 'val']:
        losses = torch.zeros(eval_iters)
        for k in range(eval_iters):
            X, Y = get_batch(split)
            scores, loss = model(X, Y)
            losses[k] = loss.item()
        out[split] = losses.mean()
    model.train()
    return out

class BigramLanguageModel(nn.Module):
    def __init__(self,vocab):
        super().__init__()
        # each token directly reads off the scores for the next token from a lookup table
        self.token_embedding_table = nn.Embedding(vocab, vocab)
    def forward(self, idx, targets=None):
        scores = self.token_embedding_table(idx) # (B,T,C)
        if targets is None:
            loss = None
        else:
            B, T, C = scores.shape
            scores = scores.view(B*T, C)
            targets = targets.view(B*T)
            loss = Func.cross_entropy(scores, targets)

        return scores, loss

    def generate(self, idx, max_new_tokens):
        # idx is (B, T) array of indices in the current context
        for _ in range(max_new_tokens):
            # crop idx to the last block_size tokens
            idx_cond = idx[:, -block_size:]
            # get the predictions
            scores, loss = self(idx_cond)
            # focus only on the last time step
            scores = scores[:, -1, :] # becomes (B, C)
            # apply softmax to get probabilities
            probs = Func.softmax(scores, dim=-1) # (B, C)
            # sample from the distribution
            idx_next = torch.multinomial(probs, num_samples=1) # (B, 1)
            # append sampled index to the running sequence
            idx = torch.cat((idx, idx_next), dim=1) # (B, T+1)
        return idx

model = BigramLanguageModel(vocab)
m = model.to(device)

# print the number of parameters in the model
print(sum(p.numel() for p in m.parameters())/1e6, 'M parameters')

# create a PyTorch optimizer
optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

for iter in range(max_iters):

    # every once in a while evaluate the loss on train and val sets
    if iter % eval_interval == 0 or iter == max_iters - 1:
        losses = estimate_loss()
        print(f"step {iter}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")

    # sample a batch of data
    xb, yb = get_batch('train')

    # evaluate the loss
    scores, loss = model(xb, yb)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

# generate from the model
context = torch.zeros((1, 1), dtype=torch.long, device=device)
current_milestone = decode(m.generate(context, max_new_tokens=500)[0].tolist())
print(current_milestone)

with open('milestone2.txt', 'w', encoding='utf-8') as mile_two:
    mile_two.write(current_milestone)

class Head(nn.Module):
  """ one head of self-attention """

  def __init__(self, head_size):
      super().__init__()
      self.key = nn.Linear(n_embd, head_size, bias=False)
      self.query = nn.Linear(n_embd, head_size, bias=False)
      self.value = nn.Linear(n_embd, head_size, bias=False)
      self.register_buffer('tril', torch.tril(torch.ones(block_size, block_size)))

      self.dropout = nn.Dropout(dropout)

  def forward(self, x):
      B,T,C = x.shape
      k = self.key(x)   # (B,T,C)
      q = self.query(x) # (B,T,C)
        # compute attention scores ("affinities")
      wei = q @ k.transpose(-2,-1) * C**-0.5 # (B, T, C) @ (B, C, T) -> (B, T, T)
      wei = wei.masked_fill(self.tril[:T, :T] == 0, float('-inf')) # (B, T, T)
      wei = Func.softmax(wei, dim=-1) # (B, T, T)
      wei = self.dropout(wei)
        # perform the weighted aggregation of the values
      v = self.value(x) # (B,T,C)
      out = wei @ v # (B, T, T) @ (B, T, C) -> (B, T, C)
      return out

class BigramLanguageModel(nn.Module):
    def __init__(self):
        super().__init__()
        # each token directly reads off the scores for the next token from a lookup table
        self.token_embedding_table = nn.Embedding(vocab, n_embd)
        self.position_embedding_table = nn.Embedding(block_size, n_embd)
        self.lm_head = nn.Linear(n_embd, vocab)

    def forward(self, idx, targets=None):
        B, T = idx.shape

        tok_emb = self.token_embedding_table(idx) # (B,T,C)
        pos_emb = self.position_embedding_table(torch.arange(T, device=device)) # (T,C)
        x = tok_emb + pos_emb # (B,T,C)
        scores = self.lm_head(tok_emb)

        if targets is None:
            loss = None
        else:
            B, T, C = scores.shape
            scores = scores.view(B*T, C)
            targets = targets.view(B*T)
            loss = Func.cross_entropy(scores, targets)

        return scores, loss

    def generate(self, idx, max_new_tokens):
        # idx is (B, T) array of indices in the current context
        for _ in range(max_new_tokens):
            # crop idx to the last block_size tokens
            idx_cond = idx[:, -block_size:]
            # get the predictions
            scores, loss = self(idx_cond)
            # focus only on the last time step
            scores = scores[:, -1, :] # becomes (B, C)
            # apply softmax to get probabilities
            probs = Func.softmax(scores, dim=-1) # (B, C)
            # sample from the distribution
            idx_next = torch.multinomial(probs, num_samples=1) # (B, 1)
            # append sampled index to the running sequence
            idx = torch.cat((idx, idx_next), dim=1) # (B, T+1)
        return idx

model = BigramLanguageModel()
m = model.to(device)

# print the number of parameters in the model
print(sum(p.numel() for p in m.parameters())/1e6, 'M parameters')

# create a PyTorch optimizer
optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

for iter in range(max_iters):

    # every once in a while evaluate the loss on train and val sets
    if iter % eval_interval == 0 or iter == max_iters - 1:
        losses = estimate_loss()
        print(f"step {iter}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")

    # sample a batch of data
    xb, yb = get_batch('train')

    # evaluate the loss
    scores, loss = model(xb, yb)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

# generate from the model
context = torch.zeros((1, 1), dtype=torch.long, device=device)
current_milestone = decode(m.generate(context, max_new_tokens=500)[0].tolist())
print(current_milestone)

with open('milestones/milestone3.txt', 'w', encoding='utf-8') as mile_three:
    mile_three.write(current_milestone)