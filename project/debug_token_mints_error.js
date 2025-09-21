import { Connection } from '@solana/web3.js';

async function debugGetRecentTokenMints() {
  console.log('🔍 Debugging getRecentTokenMints exact logic...\n');
  
  const connection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  try {
    console.log('📊 Getting current slot...');
    const slot = await connection.getSlot();
    console.log(`✅ Current slot: ${slot}`);
    
    console.log('\n📦 Processing recent slots (exact bot logic)...');
    const recentSlots = Array.from({ length: 5 }, (_, i) => slot - i);
    const mints = new Set();
    
    for (const slotNumber of recentSlots) {
      console.log(`  Processing slot ${slotNumber}...`);
      try {
        const block = await connection.getBlock(slotNumber, {
          commitment: 'confirmed',
          maxSupportedTransactionVersion: 0
        });
        
        if (block && block.transactions) {
          console.log(`    ✅ Block has ${block.transactions.length} transactions`);
          
          let tokenCreationLogs = 0;
          let potentialMints = 0;
          
          for (const tx of block.transactions) {
            if (tx.meta && tx.meta.logMessages) {
              for (const log of tx.meta.logMessages) {
                if (log.includes('Program log: InitializeMint') || 
                    log.includes('Program log: Create') ||
                    log.includes('Program log: Initialize')) {
                  
                  tokenCreationLogs++;
                  
                  const mintMatch = log.match(/[1-9A-HJ-NP-Za-km-z]{32,44}/g);
                  if (mintMatch) {
                    for (const match of mintMatch) {
                      if (match.length >= 32 && match.length <= 44) {
                        potentialMints++;
                        mints.add(match);
                      }
                    }
                  }
                }
              }
            }
          }
          
          console.log(`    📝 Found ${tokenCreationLogs} token creation logs, ${potentialMints} potential mints`);
        } else {
          console.log(`    ⚠️ Block has no data or transactions`);
        }
      } catch (slotError) {
        console.log(`    ❌ Slot ${slotNumber} error: ${slotError.message}`);
        continue;
      }
    }
    
    console.log(`\n🎯 Final result: ${mints.size} unique mints found`);
    if (mints.size > 0) {
      console.log('Found mints:', Array.from(mints).slice(0, 3));
    }
    
    return Array.from(mints);
    
  } catch (error) {
    console.log(`❌ CRITICAL ERROR (this is what bot logs): ${error.message}`);
    console.log(`Error type: ${error.constructor.name}`);
    console.log(`Stack: ${error.stack}`);
    return [];
  }
}

debugGetRecentTokenMints().catch(console.error);
