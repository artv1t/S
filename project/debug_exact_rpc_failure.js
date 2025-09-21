import { Connection } from '@solana/web3.js';

// Replicate the exact bot environment and error handling
async function debugExactRPCFailure() {
  console.log('🔍 Testing exact getRecentTokenMints logic with bot environment...\n');
  
  // Use the same RPC endpoints as the bot (from config)
  const rpcEndpoints = [
    'https://api.mainnet-beta.solana.com',
    'https://solana.drpc.org',
    'https://solana-rpc.publicnode.com'
  ];
  
  const connection = new Connection(rpcEndpoints[0], {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  try {
    console.log('📊 Step 1: Testing getSlot()...');
    const startSlot = Date.now();
    const slot = await connection.getSlot();
    console.log(`✅ getSlot() success: ${slot} (${Date.now() - startSlot}ms)`);
    
    console.log('\n📦 Step 2: Testing getBlock() calls...');
    const recentSlots = Array.from({ length: 3 }, (_, i) => slot - i);
    const mints = new Set();
    let totalLogs = 0;
    let tokenLogs = 0;
    let successfulBlocks = 0;
    let failedBlocks = 0;
    
    for (const slotNumber of recentSlots) {
      console.log(`  🔍 Testing slot ${slotNumber}...`);
      try {
        const startBlock = Date.now();
        const block = await connection.getBlock(slotNumber, {
          commitment: 'confirmed',
          maxSupportedTransactionVersion: 0
        });
        
        if (block && block.transactions) {
          successfulBlocks++;
          console.log(`    ✅ Block loaded: ${block.transactions.length} transactions (${Date.now() - startBlock}ms)`);
          
          // Process transactions (exact bot logic)
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
                  
                  // Test account key processing (this might be the failure point)
                  if (tx.transaction && tx.transaction.message && tx.transaction.message.accountKeys) {
                    try {
                      for (const accountKey of tx.transaction.message.accountKeys) {
                        if (!accountKey) continue;
                        
                        const accountStr = accountKey.toString();
                        if (!accountStr) continue;
                        
                        // This might throw an error
                        if (accountStr.length >= 32 && accountStr.length <= 44 && 
                            /^[1-9A-HJ-NP-Za-km-z]+$/.test(accountStr)) {
                          
                          if (!accountStr.startsWith('11111111111111111111111111111111') && 
                              !accountStr.startsWith('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') && 
                              !accountStr.startsWith('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')) {
                            mints.add(accountStr);
                          }
                        }
                      }
                    } catch (accountError) {
                      console.log(`    ❌ ACCOUNT PROCESSING ERROR: ${accountError.message}`);
                      throw accountError; // This might be the bot error!
                    }
                  }
                  
                  // Test regex processing (this might also be the failure point)
                  try {
                    const mintMatches = log.match(/[1-9A-HJ-NP-Za-km-z]{43,44}/g);
                    if (mintMatches) {
                      for (const match of mintMatches) {
                        if (match && match.length >= 32 && match.length <= 44 && 
                            /^[1-9A-HJ-NP-Za-km-z]+$/.test(match)) {
                          mints.add(match);
                        }
                      }
                    }
                  } catch (regexError) {
                    console.log(`    ❌ REGEX PROCESSING ERROR: ${regexError.message}`);
                    throw regexError; // This might be the bot error!
                  }
                  
                  break; // Only process first token log per transaction
                }
              }
            }
          }
        } else {
          console.log(`    ⚠️ Block ${slotNumber}: No data`);
        }
        
      } catch (slotError) {
        failedBlocks++;
        console.log(`    ❌ SLOT ERROR: ${slotError.message}`);
        console.log(`    Error type: ${slotError.constructor.name}`);
        console.log(`    Stack: ${slotError.stack?.split('\n')[0]}`);
        
        // This might be the exact error the bot is seeing
        if (slotError.message.includes('timeout') || 
            slotError.message.includes('429') || 
            slotError.message.includes('Too many requests')) {
          console.log(`    🎯 FOUND LIKELY BOT ERROR: ${slotError.message}`);
        }
        
        continue; // Bot continues on slot errors
      }
    }
    
    console.log(`\n📊 Final Results:`);
    console.log(`   Successful blocks: ${successfulBlocks}`);
    console.log(`   Failed blocks: ${failedBlocks}`);
    console.log(`   Total logs: ${totalLogs}`);
    console.log(`   Token logs: ${tokenLogs}`);
    console.log(`   Unique mints: ${mints.size}`);
    
    if (failedBlocks > 0) {
      console.log(`\n⚠️ FOUND ${failedBlocks} FAILED BLOCKS - this might explain the bot error!`);
    }
    
    if (mints.size === 0 && tokenLogs > 0) {
      console.log(`\n⚠️ FOUND TOKEN LOGS BUT NO MINTS - processing error detected!`);
    }
    
    return Array.from(mints);
    
  } catch (mainError) {
    console.log(`\n❌ MAIN ERROR (this is what bot logs as "Error getting recent token mints:"):`);
    console.log(`   Message: ${mainError.message}`);
    console.log(`   Type: ${mainError.constructor.name}`);
    console.log(`   Stack: ${mainError.stack?.split('\n').slice(0, 5).join('\n')}`);
    
    // This is the exact error the bot is catching and logging
    return [];
  }
}

debugExactRPCFailure().catch(console.error);
