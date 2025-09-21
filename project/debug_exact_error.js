import { Connection } from '@solana/web3.js';

async function debugExactTokenMintsError() {
  console.log('🔍 Debugging EXACT getRecentTokenMints error with full error details...\n');
  
  const connection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  try {
    console.log('📊 Step 1: Getting current slot...');
    const slot = await connection.getSlot();
    console.log(`✅ Current slot: ${slot}`);
    
    console.log('\n📦 Step 2: Testing getBlock with exact bot parameters...');
    const recentSlots = Array.from({ length: 3 }, (_, i) => slot - i);
    
    for (const slotNumber of recentSlots) {
      console.log(`\n  🔍 Processing slot ${slotNumber}:`);
      try {
        const startTime = Date.now();
        const block = await connection.getBlock(slotNumber, {
          commitment: 'confirmed',
          maxSupportedTransactionVersion: 0
        });
        
        if (block && block.transactions) {
          console.log(`    ✅ Block loaded: ${block.transactions.length} transactions (${Date.now() - startTime}ms)`);
          
          let totalLogs = 0;
          let tokenLogs = 0;
          let accountKeys = 0;
          let validMints = 0;
          
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
                  
                  if (tx.transaction && tx.transaction.message && tx.transaction.message.accountKeys) {
                    accountKeys += tx.transaction.message.accountKeys.length;
                    
                    for (const accountKey of tx.transaction.message.accountKeys) {
                      const accountStr = accountKey.toString();
                      
                      if (accountStr.length >= 32 && accountStr.length <= 44 && 
                          /^[1-9A-HJ-NP-Za-km-z]+$/.test(accountStr)) {
                        
                        if (!accountStr.startsWith('11111111111111111111111111111111') && 
                            !accountStr.startsWith('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') && 
                            !accountStr.startsWith('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')) {
                          validMints++;
                          
                          if (validMints <= 3) {
                            console.log(`      🎯 Found potential mint: ${accountStr}`);
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
          
          console.log(`    📊 Analysis: ${totalLogs} total logs, ${tokenLogs} token logs, ${accountKeys} account keys, ${validMints} potential mints`);
          
          if (validMints === 0) {
            console.log(`    ⚠️ NO VALID MINTS FOUND - this explains the error!`);
          }
          
        } else {
          console.log(`    ❌ Block has no data`);
        }
        
      } catch (blockError) {
        console.log(`    ❌ Block error: ${blockError.message}`);
        console.log(`    Error type: ${blockError.constructor.name}`);
        console.log(`    Stack: ${blockError.stack?.split('\n')[0]}`);
      }
    }
    
  } catch (mainError) {
    console.log(`\n❌ MAIN ERROR (this is what bot sees):`);
    console.log(`   Message: ${mainError.message}`);
    console.log(`   Type: ${mainError.constructor.name}`);
    console.log(`   Stack: ${mainError.stack?.split('\n').slice(0, 3).join('\n')}`);
  }
}

debugExactTokenMintsError().catch(console.error);
