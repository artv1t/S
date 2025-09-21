import { Connection } from '@solana/web3.js';

async function testSimpleTokenDiscovery() {
  console.log('🔍 Testing simplified token discovery logic...\n');
  
  const connection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  try {
    console.log('📊 Step 1: Getting current slot...');
    const slot = await connection.getSlot();
    console.log(`✅ Current slot: ${slot}`);
    
    console.log('\n📦 Step 2: Testing getBlock for one recent slot...');
    const slotNumber = slot - 1;
    
    const block = await connection.getBlock(slotNumber, {
      commitment: 'confirmed',
      maxSupportedTransactionVersion: 0
    });
    
    if (block && block.transactions) {
      console.log(`✅ Block loaded: ${block.transactions.length} transactions`);
      
      let totalLogs = 0;
      let tokenLogs = 0;
      
      for (const tx of block.transactions) {
        if (tx.meta && tx.meta.logMessages) {
          totalLogs += tx.meta.logMessages.length;
          
          for (const log of tx.meta.logMessages) {
            if (log.includes('Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke') ||
                log.includes('Program log: Instruction: InitializeMint')) {
              tokenLogs++;
              console.log(`🎯 Token log found: ${log.substring(0, 100)}...`);
              break; // Just show first few
            }
          }
        }
      }
      
      console.log(`\n📊 Summary: ${totalLogs} total logs, ${tokenLogs} token-related logs`);
      
      if (tokenLogs === 0) {
        console.log(`⚠️ NO TOKEN LOGS FOUND - this explains the empty results!`);
      }
      
    } else {
      console.log(`❌ Block has no data`);
    }
    
  } catch (error) {
    console.log(`\n❌ ERROR (this is what bot sees):`);
    console.log(`   Message: ${error.message}`);
    console.log(`   Type: ${error.constructor.name}`);
    console.log(`   Code: ${error.code || 'N/A'}`);
    console.log(`   Stack: ${error.stack?.split('\n').slice(0, 3).join('\n')}`);
  }
}

testSimpleTokenDiscovery().catch(console.error);
