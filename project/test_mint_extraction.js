import { Connection, PublicKey } from '@solana/web3.js';

// Test the exact mint extraction logic from the bot
function isValidMintAddress(mintAddress) {
  try {
    if (!mintAddress || typeof mintAddress !== 'string') return false;
    if (mintAddress.length < 32 || mintAddress.length > 44) return false;
    if (!/^[1-9A-HJ-NP-Za-km-z]+$/.test(mintAddress)) return false;
    
    new PublicKey(mintAddress); // Will throw if invalid
    return true;
  } catch {
    return false;
  }
}

const EXCLUDED_ADDRESSES = new Set([
  'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
  'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL',
  '11111111111111111111111111111111',
  'So11111111111111111111111111111111111111112'
]);

async function testMintExtraction() {
  console.log('🔍 Testing exact mint extraction logic from bot...\n');
  
  const connection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  try {
    const slot = await connection.getSlot();
    const slotNumber = slot - 1;
    
    const block = await connection.getBlock(slotNumber, {
      commitment: 'confirmed',
      maxSupportedTransactionVersion: 0
    });
    
    if (block && block.transactions) {
      console.log(`✅ Block loaded: ${block.transactions.length} transactions`);
      
      const mints = new Set();
      let tokenLogs = 0;
      let accountKeysProcessed = 0;
      let validMints = 0;
      let rejectedMints = 0;
      
      for (const tx of block.transactions) {
        if (tx.meta && tx.meta.logMessages) {
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
                    
                    accountKeysProcessed++;
                    
                    if (isValidMintAddress(accountStr) && !EXCLUDED_ADDRESSES.has(accountStr)) {
                      // Additional validation from bot
                      if (!accountStr.startsWith('11111111111111111111111111111111') && 
                          !accountStr.startsWith('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') && 
                          !accountStr.startsWith('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')) {
                        mints.add(accountStr);
                        validMints++;
                        
                        if (validMints <= 5) {
                          console.log(`  🎯 Valid mint found: ${accountStr}`);
                        }
                      } else {
                        rejectedMints++;
                      }
                    } else {
                      rejectedMints++;
                    }
                  }
                } catch (accountError) {
                  console.log(`  ❌ Account processing error: ${accountError.message}`);
                  throw accountError; // This might be the issue!
                }
              }
              
              // Test regex extraction (exact bot logic)
              try {
                const mintMatches = log.match(/[1-9A-HJ-NP-Za-km-z]{43,44}/g);
                if (mintMatches) {
                  for (const match of mintMatches) {
                    if (match && isValidMintAddress(match) && !EXCLUDED_ADDRESSES.has(match)) {
                      mints.add(match);
                      validMints++;
                    }
                  }
                }
              } catch (regexError) {
                console.log(`  ❌ Regex processing error: ${regexError.message}`);
                throw regexError; // This might be the issue!
              }
              
              break; // Only process first token log per transaction
            }
          }
        }
      }
      
      console.log(`\n📊 Results:`);
      console.log(`   Token logs: ${tokenLogs}`);
      console.log(`   Account keys processed: ${accountKeysProcessed}`);
      console.log(`   Valid mints: ${validMints}`);
      console.log(`   Rejected mints: ${rejectedMints}`);
      console.log(`   Unique mints found: ${mints.size}`);
      
      if (mints.size === 0) {
        console.log(`\n⚠️ NO MINTS EXTRACTED - this explains the bot error!`);
      } else {
        console.log(`\n✅ SUCCESS - mints extracted successfully`);
      }
      
    } else {
      console.log(`❌ Block has no data`);
    }
    
  } catch (error) {
    console.log(`\n❌ CRITICAL ERROR (this is what bot sees):`);
    console.log(`   Message: ${error.message}`);
    console.log(`   Type: ${error.constructor.name}`);
    console.log(`   Stack: ${error.stack?.split('\n').slice(0, 5).join('\n')}`);
  }
}

testMintExtraction().catch(console.error);
