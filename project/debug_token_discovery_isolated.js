import { Connection } from '@solana/web3.js';

// Exact copy of bot's getRecentTokenMints logic with detailed logging
async function debugTokenDiscoveryIsolated() {
  console.log('🔍 Testing EXACT bot token discovery logic with detailed error tracking...\n');
  
  const connection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  const EXCLUDED_ADDRESSES = new Set([
    'So11111111111111111111111111111111111111112', // SOL
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', // USDC
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', // USDT
  ]);
  
  function isValidMintAddress(mintAddress) {
    try {
      if (!mintAddress || typeof mintAddress !== 'string') {
        console.log(`    ❌ Invalid type: ${typeof mintAddress}`);
        return false;
      }
      if (mintAddress.length !== 44) {
        console.log(`    ❌ Invalid length: ${mintAddress.length}`);
        return false;
      }
      // Basic validation without importing PublicKey
      if (!/^[1-9A-HJ-NP-Za-km-z]+$/.test(mintAddress)) {
        console.log(`    ❌ Invalid characters in: ${mintAddress}`);
        return false;
      }
      return true;
    } catch (error) {
      console.log(`    ❌ Validation error: ${error.message}`);
      return false;
    }
  }
  
  try {
    console.log('📊 Step 1: Getting current slot...');
    const slot = await connection.getSlot();
    console.log(`✅ Current slot: ${slot}`);
    
    console.log('\n📦 Step 2: Processing recent slots (exact bot logic)...');
    const recentSlots = Array.from({ length: 3 }, (_, i) => slot - i);
    const mints = new Set();
    let totalLogs = 0;
    let tokenLogs = 0;
    
    for (const slotNumber of recentSlots) {
      console.log(`\n  🔍 Processing slot ${slotNumber}:`);
      try {
        const block = await connection.getBlock(slotNumber, {
          commitment: 'confirmed',
          maxSupportedTransactionVersion: 0
        });
        
        if (block && block.transactions) {
          console.log(`    ✅ Block loaded: ${block.transactions.length} transactions`);
          
          for (const tx of block.transactions) {
            if (tx.meta && tx.meta.logMessages) {
              totalLogs += tx.meta.logMessages.length;
              
              for (const log of tx.meta.logMessages) {
                if (log.includes('Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke') ||
                    log.includes('Program log: Instruction: InitializeMint') ||
                    log.includes('Program log: Instruction: InitializeAccount') ||
                    log.includes('CreateAccount') ||
                    log.includes('InitializeMint')) {
                  
                  tokenLogs++;
                  
                  // Test account key extraction (exact bot logic)
                  if (tx.transaction && tx.transaction.message && tx.transaction.message.accountKeys) {
                    try {
                      for (const accountKey of tx.transaction.message.accountKeys) {
                        if (!accountKey) continue;
                        
                        const accountStr = accountKey.toString();
                        if (!accountStr) continue;
                        
                        if (isValidMintAddress(accountStr) && !EXCLUDED_ADDRESSES.has(accountStr)) {
                          if (!accountStr.startsWith('11111111111111111111111111111111') && 
                              !accountStr.startsWith('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') && 
                              !accountStr.startsWith('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')) {
                            mints.add(accountStr);
                          }
                        }
                      }
                    } catch (accountError) {
                      console.log(`    ⚠️ Account processing error: ${accountError.message}`);
                    }
                  }
                  
                  // Test regex extraction (exact bot logic)
                  try {
                    const mintMatches = log.match(/[1-9A-HJ-NP-Za-km-z]{43,44}/g);
                    if (mintMatches) {
                      for (const match of mintMatches) {
                        if (match && isValidMintAddress(match) && !EXCLUDED_ADDRESSES.has(match)) {
                          mints.add(match);
                        }
                      }
                    }
                  } catch (regexError) {
                    console.log(`    ⚠️ Regex processing error: ${regexError.message}`);
                  }
                }
              }
            }
          }
        } else {
          console.log(`    ⚠️ Block has no data`);
        }
      } catch (slotError) {
        console.log(`    ❌ Slot error: ${slotError.message}`);
        console.log(`    Error type: ${slotError.constructor.name}`);
        continue;
      }
    }
    
    const mintsArray = Array.from(mints);
    console.log(`\n🎯 FINAL RESULT:`);
    console.log(`   Processed ${totalLogs} logs, found ${tokenLogs} token-related logs`);
    console.log(`   Extracted ${mintsArray.length} potential mints`);
    
    if (mintsArray.length === 0) {
      console.log(`   ⚠️ NO MINTS FOUND - this explains the bot's behavior!`);
    } else {
      console.log(`   ✅ Found mints: ${mintsArray.slice(0, 3).join(', ')}...`);
    }
    
    return mintsArray;
    
  } catch (mainError) {
    console.log(`\n❌ MAIN ERROR (this is what bot sees):`);
    console.log(`   Message: ${mainError.message}`);
    console.log(`   Type: ${mainError.constructor.name}`);
    console.log(`   Stack: ${mainError.stack?.split('\n').slice(0, 5).join('\n')}`);
    return [];
  }
}

debugTokenDiscoveryIsolated().catch(console.error);
